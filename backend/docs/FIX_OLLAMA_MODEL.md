# Fix: Ollama Model Not Found

## Issue
The pipeline is working but extracting empty fields because the configured Ollama model `llama3.2` is not available.

## Solution

### Option 1: Use an Available Model (Quick Fix)

Your available models are:
- `qwen3-vl:32b`
- `minicpm-v:latest`
- `qwen3-vl:235b-cloud`
- `llava-phi3:latest`
- `gemma3:latest`

Update `config.py` or create `.env`:

```python
# In config.py, change:
OLLAMA_MODEL: str = "gemma3:latest"  # or any available model
```

Or in `.env`:
```
OLLAMA_MODEL=gemma3:latest
```

### Option 2: Pull the llama3.2 Model

```bash
ollama pull llama3.2
```

### Option 3: Auto-Fallback (Already Implemented)

The code now automatically uses the first available model if the configured one isn't found. However, you may want to explicitly set a model.

## Current Status

✅ **Pipeline is working!** 
- 8 receipts extracted successfully
- All saved to database
- Images processed correctly

❌ **LLM extraction failing**
- Model `llama3.2` not found
- Fields are empty (None values)
- Pipeline continues gracefully

## Next Steps

1. **Update model in config:**
   ```bash
   # Edit config.py or .env
   OLLAMA_MODEL=gemma3:latest
   ```

2. **Re-run pipeline:**
   ```bash
   python debug_pipeline.py 39dc285d-6670-4dbc-92a2-7e42595efa39
   ```

3. **Or pull the model:**
   ```bash
   ollama pull llama3.2
   ```

## Verify Receipts Were Saved

Even with empty fields, receipts were saved. Check:

```bash
# List all receipts for the file
curl "http://localhost:8000/api/process/receipts/39dc285d-6670-4dbc-92a2-7e42595efa39"
```

You should see 8 receipts with IDs 1-8, but with empty merchant_name, date, total_amount, etc.

