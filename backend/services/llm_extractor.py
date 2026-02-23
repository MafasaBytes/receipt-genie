"""
LLM-based receipt field extraction using Ollama.
"""
import json
import re
import requests
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, Optional, List

import yaml

from config import settings

logger = logging.getLogger(__name__)

PROMPT_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "receipt_extraction.yml"
)


@lru_cache(maxsize=1)
def load_receipt_prompt_config() -> Dict[str, Any]:
    """Load YAML prompt configuration for receipt extraction."""
    try:
        with open(PROMPT_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                logger.warning(
                    "Receipt prompt config is not a mapping. Using empty config instead."
                )
                return {}
            return data
    except FileNotFoundError:
        logger.warning(
            f"Receipt prompt config not found at {PROMPT_CONFIG_PATH}. "
            "Falling back to built-in prompt."
        )
        return {}
    except Exception as e:
        logger.error(f"Error loading receipt prompt config: {e}")
        return {}


def build_llm_prompt(ocr_text: str) -> str:
    """Build the LLM prompt from YAML config with safe fallbacks."""
    config = load_receipt_prompt_config() or {}
    prompt_cfg = config.get("prompt", {})

    # Fallbacks preserve existing behavior if YAML is missing or partially defined.
    system = prompt_cfg.get(
        "system",
        "You are a receipt data extraction expert. Extract structured data from the receipt OCR text below.",
    )
    rules = prompt_cfg.get(
        "rules",
        "CRITICAL RULES:\n"
        "- Output ONLY valid JSON. No explanations. No markdown.\n"
        "- Use null for missing values.\n"
        "- Numbers must be floats (e.g., 9.72).\n"
        "- VAT should always be expressed as a percentage (e.g., 21.0, 9.0, 10.0).\n"
        "- If multiple VAT rates appear, list them ALL in vat_breakdown.\n",
    )
    output_schema = prompt_cfg.get(
        "output_schema",
        "{\n"
        '  "merchant_name": "string or null",\n'
        '  "date": "string or null",\n'
        '  "currency": "string or null",\n'
        "  \"total_amount\": float or null,\n"
        "  \"tax_amount\": float or null,\n"
        "  \"subtotal\": float or null,\n"
        "\n"
        "  \"items\": [\n"
        "    {\n"
        '      "name": "string or null",\n'
        "      \"quantity\": float or null,\n"
        "      \"unit_price\": float or null,\n"
        "      \"line_total\": float or null,\n"
        "      \"vat_rate\": float or null\n"
        "    }\n"
        "  ],\n"
        "\n"
        "  \"vat_breakdown\": [\n"
        "    {\n"
        "      \"vat_rate\": float,\n"
        "      \"tax_amount\": float or null,\n"
        "      \"base_amount\": float or null\n"
        "    }\n"
        "  ],\n"
        "\n"
        '  "payment_method": "string or null",\n'
        '  "address": "string or null",\n'
        '  "phone": "string or null"\n'
        "}\n",
    )
    extraction_guidelines = prompt_cfg.get(
        "extraction_guidelines",
        "Extraction guidelines:\n"
        "- If multiple VAT lines appear (e.g., 21% and 9%), include both in vat_breakdown.\n"
        "- If item lines include VAT, include the vat_rate per item.\n"
        "- If receipt totals are tax-included, compute base amounts using base = total / (1 + rate).\n"
        "- If receipt totals are tax-excluded, compute tax = base * rate.\n"
        "- If only one VAT rate is visible, still return a single vat_breakdown entry.\n",
    )
    output_instructions = prompt_cfg.get(
        "output_instructions",
        "Return ONLY the JSON object (no markdown, no code blocks, no explanations):",
    )

    prompt_parts = [
        system.strip(),
        rules.strip(),
        output_schema.strip(),
        extraction_guidelines.strip(),
        "OCR TEXT:",
        ocr_text.strip(),
        output_instructions.strip(),
    ]

    return "\n\n".join(prompt_parts)


def extract_fields_llm(ocr_text: str) -> Dict[str, Any]:
    """
    Extract structured receipt fields using Ollama LLM.
    
    Args:
        ocr_text: Raw OCR text from receipt
        
    Returns:
        Dictionary with extracted fields
    """
    prompt = build_llm_prompt(ocr_text)

    try:
        # Check if model exists, use fallback if not
        model_to_use = settings.OLLAMA_MODEL
        if not check_ollama_connection():
            raise Exception("Ollama is not running")
        
        # Verify model exists (check_ollama_connection may have updated settings.OLLAMA_MODEL)
        model_to_use = settings.OLLAMA_MODEL
        
        logger.info(f"Calling Ollama API with model: {model_to_use}")
        logger.debug(f"OCR text length: {len(ocr_text)} characters")
        
        # Allow basic model options (e.g. temperature) to be configured via YAML.
        prompt_config = load_receipt_prompt_config() or {}
        model_cfg = prompt_config.get("model", {}) if isinstance(prompt_config, dict) else {}
        temperature = model_cfg.get("temperature", 0.1)

        # Call Ollama API
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model_to_use,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": float(temperature) if temperature is not None else 0.1,  # Low temperature 
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
        raw = validate_extracted_fields(extracted_data)
        
        # Reconcile VAT and items, compute effective VAT percentage
        validated = reconcile_vat_and_items(raw, ocr_text)
        
        return validated
        
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


def parse_vat_lines(ocr_text: str) -> List[Dict[str, Any]]:
    """
    Extract VAT lines from OCR text using regex patterns as fallback.
    
    Args:
        ocr_text: Raw OCR text from receipt
        
    Returns:
        List of VAT breakdown entries with vat_rate and tax_amount
    """
    patterns = [
        r"(VAT|BTW|TVA|IVA|MwSt)\s*(\d{1,2}(?:[.,]\d)?)%\s*([0-9.,]+)",
        r"(\d{1,2}(?:[.,]\d)?)%\s*([0-9.,]+)",
        r"(VAT|BTW|TVA|IVA|MwSt)\s*(\d{1,2}(?:[.,]\d)?)%",
    ]
    results = []
    
    for pat in patterns:
        for m in re.finditer(pat, ocr_text, flags=re.IGNORECASE):
            try:
                if len(m.groups()) >= 2:
                    # Pattern 1: VAT 21% 1.68 or Pattern 2: 21% 1.68
                    if len(m.groups()) == 3:
                        rate_str = m.group(2)
                        amount_str = m.group(3)
                    elif len(m.groups()) == 2:
                        # Could be rate then amount, or just rate
                        if '%' in m.group(1):
                            rate_str = m.group(1).replace('%', '')
                            amount_str = m.group(2) if len(m.groups()) > 1 else None
                        else:
                            rate_str = m.group(1)
                            amount_str = m.group(2)
                    else:
                        continue
                    
                    rate = float(rate_str.replace(',', '.'))
                    if amount_str:
                        amount = float(amount_str.replace(',', '.').replace(' ', ''))
                        results.append({"vat_rate": round(rate, 1), "tax_amount": round(amount, 2)})
                    else:
                        results.append({"vat_rate": round(rate, 1), "tax_amount": None})
            except (ValueError, IndexError):
                continue
    
    # Collapse duplicates by rate
    combined = {}
    for r in results:
        rate = r["vat_rate"]
        if rate not in combined:
            combined[rate] = {"vat_rate": rate, "tax_amount": 0.0}
        if r["tax_amount"] is not None:
            combined[rate]["tax_amount"] += r["tax_amount"]
    
    return [{"vat_rate": rate, "tax_amount": round(t["tax_amount"], 2) if t["tax_amount"] > 0 else None} 
            for rate, t in sorted(combined.items())]


def reconcile_vat_and_items(extracted: Dict[str, Any], ocr_text: str = "") -> Dict[str, Any]:
    """
    Reconcile VAT breakdown, compute base amounts, and calculate weighted effective VAT percentage.
    
    Args:
        extracted: Raw extracted data from LLM
        ocr_text: Original OCR text for fallback VAT parsing
        
    Returns:
        Validated and reconciled data with vat_breakdown and vat_percentage_effective
    """
    validated = extracted.copy()
    warnings = []
    
    # Ensure items list exists
    if "items" not in validated or not isinstance(validated["items"], list):
        validated["items"] = []
    
    # Clean items: ensure proper structure
    cleaned_items = []
    for item in validated["items"]:
        if isinstance(item, dict):
            cleaned_item = {
                "name": str(item.get("name", "")).strip() if item.get("name") else None,
                "quantity": round(float(item["quantity"]), 2) if item.get("quantity") is not None else None,
                "unit_price": round(float(item["unit_price"]), 2) if item.get("unit_price") is not None else None,
                "line_total": round(float(item.get("line_total", item.get("total", 0))), 2) if item.get("line_total") is not None or item.get("total") is not None else None,
                "vat_rate": round(float(item["vat_rate"]), 1) if item.get("vat_rate") is not None else None
            }
            cleaned_items.append(cleaned_item)
    validated["items"] = cleaned_items
    
    # Extract or build VAT breakdown
    vat_breakdown = []
    
    # First, try to use LLM-provided vat_breakdown
    if "vat_breakdown" in validated and isinstance(validated["vat_breakdown"], list):
        for entry in validated["vat_breakdown"]:
            if isinstance(entry, dict) and "vat_rate" in entry:
                vat_breakdown.append({
                    "vat_rate": round(float(entry["vat_rate"]), 1),
                    "tax_amount": round(float(entry["tax_amount"]), 2) if entry.get("tax_amount") is not None else None,
                    "base_amount": round(float(entry["base_amount"]), 2) if entry.get("base_amount") is not None else None
                })
    
    # If no vat_breakdown from LLM, try regex fallback
    if not vat_breakdown and ocr_text:
        regex_vat = parse_vat_lines(ocr_text)
        if regex_vat:
            vat_breakdown = regex_vat
            warnings.append("VAT breakdown extracted via regex fallback")
    
    # If still no breakdown, try to infer from items
    if not vat_breakdown and validated["items"]:
        item_rates = {}
        for item in validated["items"]:
            if item.get("vat_rate") is not None:
                rate = round(float(item["vat_rate"]), 1)
                if rate not in item_rates:
                    item_rates[rate] = {"vat_rate": rate, "tax_amount": 0.0, "base_amount": 0.0}
                
                # Calculate tax and base for this item
                line_total = item.get("line_total") or item.get("total") or 0.0
                if line_total > 0:
                    # Assume tax-included (EU style)
                    base = line_total / (1 + rate / 100)
                    tax = line_total - base
                    item_rates[rate]["tax_amount"] += tax
                    item_rates[rate]["base_amount"] += base
        
        if item_rates:
            vat_breakdown = [
                {
                    "vat_rate": rate,
                    "tax_amount": round(t["tax_amount"], 2),
                    "base_amount": round(t["base_amount"], 2)
                }
                for rate, t in sorted(item_rates.items())
            ]
            warnings.append("VAT breakdown inferred from items")
    
    # If still no breakdown but we have tax_amount, create single entry
    if not vat_breakdown and validated.get("tax_amount") is not None:
        tax_amount = float(validated["tax_amount"])
        total_amount = validated.get("total_amount")
        subtotal = validated.get("subtotal")
        
        # Try to infer rate
        if total_amount and total_amount > tax_amount:
            # Assume tax-included
            base = total_amount - tax_amount
            if base > 0:
                inferred_rate = (tax_amount / base) * 100
                vat_breakdown = [{
                    "vat_rate": round(inferred_rate, 1),
                    "tax_amount": round(tax_amount, 2),
                    "base_amount": round(base, 2)
                }]
        elif subtotal and subtotal > 0:
            # Assume tax-excluded
            inferred_rate = (tax_amount / subtotal) * 100
            vat_breakdown = [{
                "vat_rate": round(inferred_rate, 1),
                "tax_amount": round(tax_amount, 2),
                "base_amount": round(subtotal, 2)
            }]
    
    # Compute base_amount for entries that don't have it
    for entry in vat_breakdown:
        if entry.get("base_amount") is None and entry.get("tax_amount") is not None and entry.get("vat_rate") is not None:
            rate = entry["vat_rate"]
            tax = entry["tax_amount"]
            # Calculate base from tax: base = tax / (rate / 100)
            if rate and rate > 0:
                base = tax / (rate / 100)
                entry["base_amount"] = round(base, 2)
    
    # Compute tax_amount for entries that don't have it
    for entry in vat_breakdown:
        if entry.get("tax_amount") is None and entry.get("base_amount") is not None and entry.get("vat_rate") is not None:
            rate = entry["vat_rate"]
            base = entry["base_amount"]
            if rate and rate > 0:
                tax = base * (rate / 100)
                entry["tax_amount"] = round(tax, 2)

    # --- VAT sanity checks & normalization ---
    # Common Dutch/EU VAT rates (tight mapping, focused on NL use-case)
    # - 0%  : zero / exempt
    # - 9%  : low rate
    # - 10% : some special cases / canteens
    # - 21% : standard rate
    common_vat_rates = [0.0, 9.0, 10.0, 21.0]

    total_amount = validated.get("total_amount")

    for entry in vat_breakdown:
        rate = entry.get("vat_rate")
        base = entry.get("base_amount")
        tax = entry.get("tax_amount")

        # Skip entries without a rate
        if rate is None:
            continue

        # Snap rate to nearest common VAT rate if it's very close (tolerance 0.3%)
        nearest_rate = min(common_vat_rates, key=lambda r: abs(r - rate))
        if abs(nearest_rate - rate) <= 0.3:
            rate = nearest_rate
            entry["vat_rate"] = rate

        # Basic bounds check – anything above 30% is highly suspicious for NL/EU
        if rate < 0 or rate > 30:
            warnings.append(f"vat_rate_out_of_range:{rate}")
            entry["vat_rate"] = None
            continue

        # If tax looks more like a base amount (too large vs total), treat it as base
        if tax is not None and total_amount is not None:
            try:
                if tax > float(total_amount) * 0.5:
                    # Likely base amount misclassified as tax
                    base = tax
                    tax = None
                    entry["base_amount"] = round(base, 2)
                    entry["tax_amount"] = None
                    warnings.append("vat_tax_amount_reinterpreted_as_base")
            except Exception:
                pass

        # Make base/tax consistent with the VAT rate
        base = entry.get("base_amount")
        tax = entry.get("tax_amount")

        if rate and rate > 0:
            if base is not None and tax is not None:
                # Validate: tax should be base * rate / 100 within a small tolerance
                expected_tax = round(base * (rate / 100), 2)
                if abs(expected_tax - tax) > 0.03:
                    entry["tax_amount"] = expected_tax
                    warnings.append("vat_tax_corrected_from_math")
            elif tax is not None:
                # Derive base from tax
                base = tax / (rate / 100)
                entry["base_amount"] = round(base, 2)
            elif base is not None:
                # Derive tax from base
                tax = base * (rate / 100)
                entry["tax_amount"] = round(tax, 2)

    # After fixing individual entries, ensure aggregate tax aligns with totals where possible
    total_base_from_bd = sum(e.get("base_amount", 0) or 0 for e in vat_breakdown)
    total_tax_from_bd = sum(e.get("tax_amount", 0) or 0 for e in vat_breakdown)

    # If we have exactly one VAT rate and a reliable total, force math to be consistent
    if len(vat_breakdown) == 1 and total_amount is not None:
        entry = vat_breakdown[0]
        rate = entry.get("vat_rate")
        if rate and rate > 0:
            # Assume tax‑included total: total = base + tax
            base = float(total_amount) / (1 + rate / 100)
            tax = float(total_amount) - base
            entry["base_amount"] = round(base, 2)
            entry["tax_amount"] = round(tax, 2)
            total_base_from_bd = entry["base_amount"]
            total_tax_from_bd = entry["tax_amount"]
            validated["subtotal"] = entry["base_amount"]
            validated["tax_amount"] = entry["tax_amount"]
            warnings.append("vat_single_rate_totals_normalized")
    
    validated["vat_breakdown"] = vat_breakdown
    
    # Calculate weighted effective VAT percentage
    vat_percentage_effective = None
    if vat_breakdown:
        total_base = sum(e.get("base_amount", 0) or 0 for e in vat_breakdown)
        total_tax = sum(e.get("tax_amount", 0) or 0 for e in vat_breakdown)
        
        if total_base > 0:
            vat_percentage_effective = (total_tax / total_base) * 100
        elif total_tax > 0 and validated.get("total_amount"):
            # Fallback: use total_amount
            total = float(validated["total_amount"])
            if total > total_tax:
                base = total - total_tax
                if base > 0:
                    vat_percentage_effective = (total_tax / base) * 100

    # Snap effective VAT to nearest common rate when close, and clamp to realistic range
    if vat_percentage_effective is not None:
        nearest_rate = min(common_vat_rates, key=lambda r: abs(r - vat_percentage_effective))
        if abs(nearest_rate - vat_percentage_effective) <= 0.3:
            vat_percentage_effective = nearest_rate
        # Reject clearly invalid rates (>30%) by nulling and warning
        if vat_percentage_effective < 0 or vat_percentage_effective > 30:
            warnings.append(f"vat_percentage_effective_out_of_range:{vat_percentage_effective}")
            vat_percentage_effective = None
        else:
            vat_percentage_effective = round(vat_percentage_effective, 1)
    
    validated["vat_percentage_effective"] = vat_percentage_effective
    
    # Round all amounts to 2 decimals
    for field in ["total_amount", "tax_amount", "subtotal"]:
        if validated.get(field) is not None:
            validated[field] = round(float(validated[field]), 2)
    
    # Round VAT rates in breakdown to 1 decimal
    for entry in validated["vat_breakdown"]:
        if entry.get("vat_rate") is not None:
            entry["vat_rate"] = round(float(entry["vat_rate"]), 1)
    
    # Store warnings if any
    if warnings:
        validated["_warnings"] = warnings
    
    return validated


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
        "currency": None,
        "items": [],
        "vat_breakdown": [],
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
    
    # Extract currency
    if "currency" in data:
        validated["currency"] = str(data["currency"]).strip().upper() if data["currency"] else None
    
    # Extract items
    if "items" in data and isinstance(data["items"], list):
        validated["items"] = []
        for item in data["items"]:
            if isinstance(item, dict):
                validated["items"].append({
                    "name": str(item.get("name", "")).strip() if item.get("name") else None,
                    "quantity": float(item["quantity"]) if item.get("quantity") is not None else None,
                    "unit_price": float(item.get("unit_price", item.get("price", 0))) if item.get("unit_price") is not None or item.get("price") is not None else None,
                    "line_total": float(item.get("line_total", item.get("total", 0))) if item.get("line_total") is not None or item.get("total") is not None else None,
                    "vat_rate": float(item["vat_rate"]) if item.get("vat_rate") is not None else None,
                })
    
    # Extract vat_breakdown
    if "vat_breakdown" in data and isinstance(data["vat_breakdown"], list):
        validated["vat_breakdown"] = []
        for entry in data["vat_breakdown"]:
            if isinstance(entry, dict) and "vat_rate" in entry:
                validated["vat_breakdown"].append({
                    "vat_rate": float(entry["vat_rate"]),
                    "tax_amount": float(entry["tax_amount"]) if entry.get("tax_amount") is not None else None,
                    "base_amount": float(entry["base_amount"]) if entry.get("base_amount") is not None else None,
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

