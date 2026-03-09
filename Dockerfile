# =============================================================
# Stage 1: Build the React frontend
# =============================================================
FROM node:20-slim AS frontend-build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json \
     tailwind.config.ts postcss.config.js components.json eslint.config.js ./
COPY src/ src/
COPY public/ public/

# Build with the backend API URL pointing at the same origin (nginx will proxy)
ENV VITE_API_URL=""
RUN npm run build


# =============================================================
# Stage 2: Production image — Python backend + Tesseract + nginx
# =============================================================
FROM python:3.13-slim

# ---- System deps: Tesseract, OpenCV libs, nginx, C++ compiler for chroma-hnswlib ----
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-nld \
        tesseract-ocr-eng \
        libgl1 \
        libglib2.0-0 \
        nginx \
        curl \
        build-essential \
        g++ \
    && rm -rf /var/lib/apt/lists/*

# ---- Python dependencies ----
WORKDIR /app/backend

COPY backend/requirements.txt .
# Add pytesseract to requirements at build time
RUN pip install --no-cache-dir -r requirements.txt pytesseract

# ---- Backend source ----
COPY backend/ .

# Create runtime directories
RUN mkdir -p temp exports vector_store data

# ---- Run migrations on startup (handled by entrypoint) ----

# ---- Frontend static files ----
COPY --from=frontend-build /app/dist /app/frontend

# ---- nginx config: serves frontend + proxies /api to uvicorn ----
RUN cat > /etc/nginx/sites-available/default <<'NGINX'
server {
    listen 80;
    server_name _;

    # Frontend static files
    root /app/frontend;
    index index.html;

    # API proxy to FastAPI backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 600s;
        client_max_body_size 50M;
    }

    # Health check passthrough
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }

    # SPA fallback — all non-file routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX

# ---- Entrypoint script ----
COPY entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# ---- Environment defaults ----
ENV DATABASE_URL="sqlite:///./data/receipt_scanner.db" \
    OLLAMA_BASE_URL="http://ollama:11434" \
    OLLAMA_MODEL="llama3.2:latest" \
    RAG_ENABLED="true" \
    PYTHONUNBUFFERED=1

EXPOSE 80

CMD ["/app/entrypoint.sh"]
