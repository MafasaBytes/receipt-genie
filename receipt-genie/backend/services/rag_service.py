"""
RAG (Retrieval-Augmented Generation) orchestration service.

Ties together the vector store and the LLM extractor to produce
context-enriched prompts. When a new receipt is processed, this module:

1. Embeds the OCR text.
2. Retrieves the top-k most similar past receipts from ChromaDB.
3. Builds a few-shot augmented prompt that includes real examples so
   the LLM can pattern-match against known-good extractions.
4. Optionally cross-validates the LLM output against retrieved
   neighbours to catch obvious errors.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from services.vector_store import query_similar_receipts

logger = logging.getLogger(__name__)


def retrieve_examples(
    ocr_text: str,
    exclude_receipt_ids: List[int] | None = None,
) -> List[Dict[str, Any]]:
    """Return similar past receipts suitable for few-shot injection."""
    if not settings.RAG_ENABLED:
        return []

    matches = query_similar_receipts(
        ocr_text,
        top_k=settings.RAG_TOP_K,
        min_similarity=settings.RAG_MIN_SIMILARITY,
        exclude_ids=exclude_receipt_ids,
    )
    logger.info(
        f"RAG retrieved {len(matches)} similar receipt(s) "
        f"(similarities: {[m['similarity'] for m in matches]})"
    )
    return matches


def build_few_shot_block(matches: List[Dict[str, Any]]) -> str:
    """
    Format retrieved matches into a few-shot examples block that can be
    injected directly into the LLM prompt.
    """
    if not matches:
        return ""

    parts = [
        "REFERENCE EXAMPLES",
        "Below are real receipts that were previously processed successfully.",
        "Use them as guidance for format, field names, and value styles — but",
        "extract data ONLY from the new OCR text provided afterwards.",
        "",
    ]

    for idx, match in enumerate(matches, 1):
        doc = match.get("document", "")

        # Split into OCR portion and JSON portion
        if "---EXTRACTED_JSON---" in doc:
            _ocr_part, json_part = doc.split("---EXTRACTED_JSON---", 1)
        else:
            json_part = doc

        # Only inject the extraction result (the OCR text of other receipts
        # would just add noise and eat context window)
        label = "user-verified" if match.get("is_user_corrected") else "auto-extracted"
        sim = match.get("similarity", 0)
        parts.append(f"--- Example {idx} (similarity={sim:.2f}, source={label}) ---")
        parts.append(json_part.strip())
        parts.append("")

    parts.append("--- End of examples ---")
    parts.append("")
    return "\n".join(parts)


def cross_validate(
    extracted: Dict[str, Any],
    matches: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compare the freshly extracted fields against retrieved neighbours and
    surface warnings or soft corrections.

    For now this is conservative — it adds `_rag_warnings` metadata but
    does NOT silently overwrite LLM output.
    """
    if not matches:
        return extracted

    warnings: List[str] = []

    neighbour_merchants = _collect_field(matches, "merchant_name")
    neighbour_currencies = _collect_field(matches, "currency")

    merchant = extracted.get("merchant_name")
    currency = extracted.get("currency")

    # Warn if merchant name is very different from all neighbours
    if merchant and neighbour_merchants:
        normalised = merchant.strip().lower()
        if not any(normalised in nm.lower() or nm.lower() in normalised for nm in neighbour_merchants):
            warnings.append(
                f"merchant_name '{merchant}' differs from similar receipts: "
                f"{neighbour_merchants[:3]}"
            )

    # Auto-fill currency from neighbours when LLM left it null
    if not currency and neighbour_currencies:
        from collections import Counter
        most_common_currency = Counter(neighbour_currencies).most_common(1)[0][0]
        extracted["currency"] = most_common_currency
        warnings.append(f"currency inferred from similar receipts: {most_common_currency}")

    # Flag suspiciously large totals compared to neighbours
    total = extracted.get("total_amount")
    if total is not None:
        neighbour_totals = _collect_numeric_field(matches, "total_amount")
        if neighbour_totals:
            avg_total = sum(neighbour_totals) / len(neighbour_totals)
            if avg_total > 0 and total > avg_total * 10:
                warnings.append(
                    f"total_amount {total} is >10x average of similar receipts ({avg_total:.2f})"
                )

    if warnings:
        existing = extracted.get("_rag_warnings", [])
        extracted["_rag_warnings"] = existing + warnings

    return extracted


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_field(matches: List[Dict[str, Any]], field: str) -> List[str]:
    """Pull a string metadata field from retrieved matches."""
    values = []
    for m in matches:
        meta = m.get("metadata", {})
        v = meta.get(field)
        if v:
            values.append(str(v))
    return values


def _collect_numeric_field(matches: List[Dict[str, Any]], field: str) -> List[float]:
    """Pull a numeric metadata field from retrieved matches."""
    values = []
    for m in matches:
        meta = m.get("metadata", {})
        v = meta.get(field)
        if v is not None:
            try:
                values.append(float(v))
            except (ValueError, TypeError):
                pass
    return values
