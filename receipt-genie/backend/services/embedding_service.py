"""
Embedding service using Ollama's embedding API.

Generates vector embeddings for receipt OCR text using a local embedding model
(nomic-embed-text by default). These embeddings power the RAG pipeline by
enabling semantic similarity search across previously processed receipts.
"""
import logging
from typing import List, Optional

import requests

from config import settings

logger = logging.getLogger(__name__)

_embedding_model_verified = False


def verify_embedding_model() -> bool:
    """Pull the embedding model if it isn't already available in Ollama."""
    global _embedding_model_verified
    if _embedding_model_verified:
        return True

    try:
        resp = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            logger.warning("Cannot reach Ollama to verify embedding model")
            return False

        model_names = [m.get("name", "") for m in resp.json().get("models", [])]
        model = settings.EMBEDDING_MODEL

        # Exact match or prefix match (e.g. "nomic-embed-text" matches "nomic-embed-text:latest")
        found = any(model == n or n.startswith(f"{model}:") for n in model_names)
        if not found:
            logger.info(f"Embedding model '{model}' not found locally, pulling...")
            pull_resp = requests.post(
                f"{settings.OLLAMA_BASE_URL}/api/pull",
                json={"name": model, "stream": False},
                timeout=600,
            )
            if pull_resp.status_code != 200:
                logger.error(f"Failed to pull embedding model: {pull_resp.text[:300]}")
                return False
            logger.info(f"Successfully pulled embedding model '{model}'")

        _embedding_model_verified = True
        return True
    except requests.exceptions.ConnectionError:
        logger.warning(f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL} for embedding model check")
        return False
    except Exception as e:
        logger.error(f"Error verifying embedding model: {e}")
        return False


def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate a vector embedding for the given text via Ollama's /api/embed endpoint.

    Returns None on failure so callers can degrade gracefully.
    """
    if not text or not text.strip():
        return None

    try:
        resp = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={"model": settings.EMBEDDING_MODEL, "input": text.strip()},
            timeout=60,
        )
        if resp.status_code != 200:
            logger.error(f"Ollama embed API error {resp.status_code}: {resp.text[:300]}")
            return None

        data = resp.json()

        # /api/embed returns {"embeddings": [[...]]}
        embeddings = data.get("embeddings") or data.get("embedding")
        if isinstance(embeddings, list) and len(embeddings) > 0:
            vec = embeddings[0] if isinstance(embeddings[0], list) else embeddings
            if vec and len(vec) > 0:
                return vec

        logger.warning("Ollama embed response missing embedding data")
        return None

    except requests.exceptions.ConnectionError:
        logger.warning("Cannot connect to Ollama for embedding generation")
        return None
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None


def generate_embeddings_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """Generate embeddings for multiple texts. Returns a list aligned with input."""
    return [generate_embedding(t) for t in texts]
