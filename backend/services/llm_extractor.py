"""
LLM-based receipt field extraction using Ollama.
"""
import json
import requests
import logging
from typing import Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)


def extract_fields_llm(ocr_text: str) -> Dict[str, Any]:
    """
    Extract structured receipt fields using Ollama LLM.
    
    Args:
        ocr_text: Raw OCR text from receipt
        
    Returns:
        Dictionary with extracted fields
    """
    prompt = f"""Extract structured data from the following receipt text. 
Return ONLY a valid JSON object with these fields:
- merchant_name (string)
- date (string, format: YYYY-MM-DD if possible)
- total_amount (float)
- tax_amount (float, optional)
- subtotal (float, optional)
- currency (string, 3-letter code like EUR, USD, GBP, optional)
- items (array of objects with: name, quantity, price, total)
- payment_method (string, optional)
- address (string, optional)
- phone (string, optional)
- vat_amount (float, optional)
- vat_percentage (float, optional)

Receipt text:
{ocr_text}

Return ONLY the JSON object, no other text:"""

    try:
        # Check if model exists, use fallback if not
        model_to_use = settings.OLLAMA_MODEL
        if not check_ollama_connection():
            raise Exception("Ollama is not running")
        
        # Verify model exists (check_ollama_connection may have updated settings.OLLAMA_MODEL)
        model_to_use = settings.OLLAMA_MODEL
        
        logger.info(f"Calling Ollama API with model: {model_to_use}")
        logger.debug(f"OCR text length: {len(ocr_text)} characters")
        
        # Call Ollama API
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model_to_use,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for structured extraction
                }
            },
            timeout=settings.OLLAMA_TIMEOUT
        )
        
        if response.status_code != 200:
            error_msg = f"Ollama API error: {response.status_code}"
            if response.text:
                error_msg += f" - {response.text[:200]}"
            raise Exception(error_msg)
        
        result = response.json()
        response_text = result.get("response", "").strip()
        logger.debug(f"LLM response length: {len(response_text)} characters")
        
        # Try to extract JSON from response
        # Sometimes LLM adds markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        try:
            extracted_data = json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback: try to find JSON object in text
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                extracted_data = json.loads(response_text[start_idx:end_idx])
            else:
                raise ValueError("Could not parse JSON from LLM response")
        
        # Validate and clean extracted data
        return validate_extracted_fields(extracted_data)
        
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL}. Is Ollama running?"
        logger.error(error_msg)
        raise Exception(error_msg)
    except requests.exceptions.Timeout as e:
        error_msg = f"Ollama API timeout after {settings.OLLAMA_TIMEOUT}s"
        logger.error(error_msg)
        raise Exception(error_msg)
    except requests.exceptions.RequestException as e:
        error_msg = f"Error calling Ollama API: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Error extracting fields with LLM: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def validate_extracted_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and clean extracted fields.
    
    Args:
        data: Raw extracted data from LLM
        
    Returns:
        Validated and cleaned data
    """
    validated = {
        "merchant_name": None,
        "date": None,
        "total_amount": None,
        "tax_amount": None,
        "subtotal": None,
        "items": [],
        "payment_method": None,
        "address": None,
        "phone": None,
    }
    
    # Extract merchant name
    if "merchant_name" in data:
        validated["merchant_name"] = str(data["merchant_name"]).strip() if data["merchant_name"] else None
    
    # Extract date
    if "date" in data:
        validated["date"] = str(data["date"]).strip() if data["date"] else None
    
    # Extract amounts (convert to float)
    for field in ["total_amount", "tax_amount", "subtotal"]:
        if field in data and data[field] is not None:
            try:
                validated[field] = float(data[field])
            except (ValueError, TypeError):
                validated[field] = None
    
    # Extract items
    if "items" in data and isinstance(data["items"], list):
        validated["items"] = []
        for item in data["items"]:
            if isinstance(item, dict):
                validated["items"].append({
                    "name": str(item.get("name", "")).strip() if item.get("name") else None,
                    "quantity": float(item["quantity"]) if item.get("quantity") else None,
                    "price": float(item["price"]) if item.get("price") else None,
                    "total": float(item["total"]) if item.get("total") else None,
                })
    
    # Extract optional fields
    for field in ["payment_method", "address", "phone"]:
        if field in data and data[field]:
            validated[field] = str(data[field]).strip()
    
    return validated


def check_ollama_connection() -> bool:
    """
    Check if Ollama is running and accessible.
    
    Returns:
        True if Ollama is accessible, False otherwise
    """
    try:
        response = requests.get(
            f"{settings.OLLAMA_BASE_URL}/api/tags",
            timeout=5
        )
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            logger.info(f"Ollama is running. Available models: {', '.join(model_names)}")
            if settings.OLLAMA_MODEL not in model_names:
                logger.warning(f"Model '{settings.OLLAMA_MODEL}' not found. Available: {', '.join(model_names)}")
                if model_names:
                    # Auto-select first available model as fallback
                    fallback_model = model_names[0]
                    logger.info(f"Using fallback model: {fallback_model}")
                    # Update settings for this session
                    settings.OLLAMA_MODEL = fallback_model
            return True
        return False
    except requests.exceptions.ConnectionError:
        logger.warning(f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL}")
        return False
    except Exception as e:
        logger.warning(f"Error checking Ollama connection: {str(e)}")
        return False

