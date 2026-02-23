# Timeout Configuration Guide

## Overview

The system has multiple timeout settings to handle long-running operations, especially when processing many receipts. This document explains all timeout configurations and how to adjust them.

## Timeout Settings

### 1. Frontend Polling Timeout

**Location**: `src/services/api.ts`

**Current Setting**: 10 minutes (600,000ms)

**What it does**: Maximum time the frontend will wait for a processing job to complete before timing out.

**When to increase**: If you're processing PDFs with many receipts (10+), you may need to increase this.

**How to change**:
```typescript
const maxWaitTime = 600000; // Change this value (in milliseconds)
```

**Recommended values**:
- Small PDFs (1-5 receipts): 5 minutes (300000ms)
- Medium PDFs (5-15 receipts): 10 minutes (600000ms)
- Large PDFs (15+ receipts): 15-20 minutes (900000-1200000ms)

### 2. Ollama LLM API Timeout

**Location**: `backend/config.py`

**Current Setting**: 5 minutes (300 seconds)

**What it does**: Maximum time to wait for Ollama to process a single receipt's LLM extraction.

**When to increase**: 
- Using slower/larger LLM models
- Processing complex receipts with lots of text
- Running on slower hardware

**How to change**:
```python
OLLAMA_TIMEOUT: int = 300  # Change this value (in seconds)
```

**Recommended values**:
- Fast models (gemma3, llama3.2): 300 seconds (5 minutes)
- Medium models: 600 seconds (10 minutes)
- Large/slow models: 900 seconds (15 minutes)

**Environment variable override**:
```bash
export OLLAMA_TIMEOUT=600
```

### 3. Frontend Polling Interval

**Location**: `src/services/api.ts`

**Current Setting**: 2 seconds

**What it does**: How often the frontend checks for job status updates.

**When to adjust**: 
- Increase if you want to reduce server load
- Decrease if you want more frequent progress updates

**How to change**:
```typescript
const pollInterval = 2000; // Change this value (in milliseconds)
```

## Timeout Calculation Example

For a PDF with 8 receipts:

- **Per-receipt processing time**: ~30-60 seconds (OCR + LLM)
- **Total processing time**: 8 × 45s = ~6 minutes
- **With buffer**: ~8-10 minutes total

**Current settings should handle this**, but if you have more receipts or slower processing, increase the timeouts accordingly.

## Troubleshooting Timeout Issues

### Error: "Processing timeout - job took too long"

**Solution**: Increase frontend polling timeout in `src/services/api.ts`

### Error: "Ollama API timeout after Xs"

**Solution**: 
1. Increase `OLLAMA_TIMEOUT` in `backend/config.py`
2. Check if Ollama is running: `ollama list`
3. Consider using a faster model
4. Check system resources (CPU/RAM)

### Job Status Shows "processing" But Never Completes

**Possible causes**:
1. Background task crashed (check backend logs)
2. Database connection lost
3. Out of memory
4. LLM extraction stuck

**Solution**: 
1. Check backend logs for errors
2. Restart the backend server
3. Check system resources
4. Try processing a smaller PDF first

## Best Practices

1. **Start with default timeouts** and only increase if needed
2. **Monitor processing times** in logs to determine optimal timeout values
3. **Use faster LLM models** for better performance (gemma3, llama3.2)
4. **Process in batches** if you have many PDFs
5. **Check system resources** - timeouts may indicate resource constraints

## Monitoring

Check processing times in backend logs:
```
INFO - LLM extraction completed in 45.23s
WARNING - LLM extraction took 180.45s (slow, consider increasing timeout)
```

If you see many warnings about slow processing, consider:
- Increasing `OLLAMA_TIMEOUT`
- Using a faster model
- Optimizing your hardware

