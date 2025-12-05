"""
LLM-based receipt field extraction using Ollama.
"""
import json
import re
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
    prompt = f"""You are a receipt data extraction expert. Extract structured data from the following receipt text (which may contain OCR errors).

CRITICAL JSON FORMATTING RULES:
1. Use `null` (not `null.00`, `null.0`, or any other variant) for missing/unknown values
2. Use proper JSON syntax: no trailing commas, proper quotes, etc.
3. Return ONLY valid JSON, no markdown code blocks, no explanations, no additional text
4. All numbers must be valid floats (e.g., 9.72, not "9,72" or "€9.72")
5. Dates should be in YYYY-MM-DD format if possible, otherwise use the original format as string

REQUIRED JSON SCHEMA:
{{
  "merchant_name": "string or null",
  "date": "string (YYYY-MM-DD preferred) or null",
  "total_amount": float or null,
  "tax_amount": float or null,
  "subtotal": float or null,
  "currency": "string (3-letter code: EUR, USD, GBP, etc.) or null",
  "items": [{{"name": "string", "quantity": float, "price": float, "total": float}}] or [],
  "payment_method": "string or null",
  "address": "string or null",
  "phone": "string or null",
  "vat_amount": float or null,
  "vat_percentage": float or null
}}

EXTRACTION GUIDELINES:

1. MERCHANT_NAME: Extract the store/company name (usually at the top). Common Dutch stores: Albert Heijn (AH), Jumbo, Plus, Coop, etc.

2. DATE: 
   - Dutch format: "15-07-2022" or "15/07/2022" → convert to "2022-07-15"
   - English format: "Jul 15, 2022" → convert to "2022-07-15"
   - If unclear, keep original format as string
   - Look for keywords: "Datum", "Date", "Bon datum"

3. TOTAL_AMOUNT: 
   - Look for "Totaal", "Total", "Totaalbedrag", "Eindtotaal", "Totaal incl. BTW"
   - Remove currency symbols (€, EUR, etc.) and commas used as decimal separators
   - Convert "9,72" to 9.72, "€12.50" to 12.50

4. TAX_AMOUNT / VAT_AMOUNT:
   - Dutch receipts use "BTW" (Belasting Toegevoegde Waarde)
   - Look for "BTW", "VAT", "Tax", "Belasting"
   - Can be same as tax_amount field

5. CURRENCY:
   - Default to "EUR" for Dutch receipts (Netherlands uses Euro)
   - Look for currency symbols: € = EUR, $ = USD, £ = GBP
   - If not found but receipt is clearly Dutch, use "EUR"

6. ITEMS:
   - Extract line items if clearly listed
   - Each item: name, quantity (if shown), price per unit, total
   - If items are not clearly separated, use empty array []

7. PAYMENT_METHOD:
   - Look for: "Contant", "Cash", "PIN", "Debit", "Credit Card", "Creditcard", "iDEAL", etc.

8. ADDRESS: Full store address if available

9. PHONE: Phone number in any format

10. VAT_PERCENTAGE:
    - Common Dutch VAT rates: 9% (low rate), 21% (standard rate)
    - Calculate if you have tax_amount and total_amount: (tax_amount / (total_amount - tax_amount)) * 100

HANDLING OCR ERRORS:
- If text is unclear or garbled, use null for that field
- Try to infer from context (e.g., "AH" likely means "Albert Heijn")
- Numbers with OCR errors: if clearly a number but some digits are wrong, use your best interpretation

EXAMPLE OUTPUT:
{{
  "merchant_name": "Albert Heijn",
  "date": "2022-07-15",
  "total_amount": 9.72,
  "tax_amount": 1.68,
  "subtotal": 8.04,
  "currency": "EUR",
  "items": [{{"name": "Brood", "quantity": 1, "price": 2.50, "total": 2.50}}, {{"name": "Melk", "quantity": 2, "price": 1.25, "total": 2.50}}],
  "payment_method": "PIN",
  "address": "Hoofdstraat 123, Amsterdam",
  "phone": null,
  "vat_amount": 1.68,
  "vat_percentage": 21.0
}}

NOW EXTRACT DATA FROM THIS RECEIPT TEXT:

{ocr_text}

Return ONLY the JSON object (no markdown, no code blocks, no explanations):"""

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
        
        # Log raw response for debugging (first 500 chars)
        logger.debug(f"LLM raw response (first 500 chars): {response_text[:500]}")
        
        # Parse JSON with multiple fallback strategies
        extracted_data = None
        json_parse_errors = []
        
        # Strategy 1: Direct parse
        try:
            extracted_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            json_parse_errors.append(f"Direct parse: {str(e)}")
        
        # Strategy 2: Find JSON object boundaries
        if extracted_data is None:
            try:
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    extracted_data = json.loads(response_text[start_idx:end_idx])
            except json.JSONDecodeError as e:
                json_parse_errors.append(f"Boundary parse: {str(e)}")
        
        # Strategy 3: Try to fix common JSON issues
        if extracted_data is None:
            try:
                # Remove trailing commas before closing braces/brackets
                fixed_text = re.sub(r',\s*}', '}', response_text)
                fixed_text = re.sub(r',\s*]', ']', fixed_text)
                # Fix invalid null.00, null.0, etc. -> null
                fixed_text = re.sub(r'\bnull\.\d+\b', 'null', fixed_text)
                # Try parsing again
                start_idx = fixed_text.find("{")
                end_idx = fixed_text.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    extracted_data = json.loads(fixed_text[start_idx:end_idx])
            except (json.JSONDecodeError, Exception) as e:
                json_parse_errors.append(f"Fixed parse: {str(e)}")
        
        # Strategy 4: Try to extract just the JSON part line by line
        if extracted_data is None:
            try:
                lines = response_text.split('\n')
                json_lines = []
                in_json = False
                for line in lines:
                    if '{' in line:
                        in_json = True
                    if in_json:
                        json_lines.append(line)
                    if in_json and '}' in line:
                        break
                if json_lines:
                    json_text = '\n'.join(json_lines)
                    # Remove trailing commas
                    json_text = re.sub(r',\s*}', '}', json_text)
                    json_text = re.sub(r',\s*]', ']', json_text)
                    extracted_data = json.loads(json_text)
            except (json.JSONDecodeError, Exception) as e:
                json_parse_errors.append(f"Line-by-line parse: {str(e)}")
        
        if extracted_data is None:
            error_details = "; ".join(json_parse_errors)
            logger.error(f"All JSON parsing strategies failed. Errors: {error_details}")
            logger.error(f"Response text (first 1000 chars): {response_text[:1000]}")
            raise ValueError(f"Could not parse JSON from LLM response. Last error: {json_parse_errors[-1] if json_parse_errors else 'Unknown'}")
        
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

