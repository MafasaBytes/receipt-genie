"""
ChromaDB-backed vector store for receipt embeddings.

Stores OCR text embeddings alongside structured metadata (merchant, amounts,
currency, etc.) so that the RAG pipeline can retrieve semantically similar
past receipts as few-shot examples for the LLM.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from services.embedding_service import generate_embedding

logger = logging.getLogger(__name__)

_collection = None


def _get_collection():
    """Lazy-init and return the ChromaDB collection (singleton)."""
    global _collection
    if _collection is not None:
        return _collection

    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.PersistentClient(
            path=str(settings.CHROMA_PERSIST_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB collection '{settings.CHROMA_COLLECTION_NAME}' ready "
            f"({_collection.count()} documents)"
        )
        return _collection
    except Exception as e:
        logger.error(f"Failed to initialise ChromaDB: {e}")
        return None


def init_vector_store() -> bool:
    """Eagerly initialise the vector store. Returns True on success."""
    return _get_collection() is not None


def index_receipt(
    receipt_id: int,
    ocr_text: str,
    extracted_fields: Dict[str, Any],
    *,
    is_user_corrected: bool = False,
) -> bool:
    """
    Add or update a receipt in the vector store.

    Parameters
    ----------
    receipt_id : int
        Database primary key – used as the ChromaDB document ID.
    ocr_text : str
        Raw OCR text (the document we embed).
    extracted_fields : dict
        The structured extraction result (stored as metadata for retrieval).
    is_user_corrected : bool
        If True the receipt was manually corrected by the user and should be
        treated as a high-quality example (boosted during retrieval).
    """
    collection = _get_collection()
    if collection is None:
        return False

    embedding = generate_embedding(ocr_text)
    if embedding is None:
        logger.warning(f"Could not generate embedding for receipt {receipt_id}")
        return False

    # Flatten extracted_fields into ChromaDB-friendly metadata (strings/numbers/bools).
    metadata = _build_metadata(extracted_fields, is_user_corrected)

    doc_id = str(receipt_id)

    # Store the full extraction as the document body so it can be returned
    # as a few-shot example without a DB round-trip.
    document = _build_document_text(ocr_text, extracted_fields)

    try:
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[document],
            metadatas=[metadata],
        )
        logger.debug(f"Indexed receipt {receipt_id} (corrected={is_user_corrected})")
        return True
    except Exception as e:
        logger.error(f"Failed to index receipt {receipt_id}: {e}")
        return False


def query_similar_receipts(
    ocr_text: str,
    top_k: int | None = None,
    min_similarity: float | None = None,
    exclude_ids: List[int] | None = None,
) -> List[Dict[str, Any]]:
    """
    Find the most similar previously-processed receipts.

    Returns a list of dicts with keys: receipt_id, distance, similarity,
    document (the stored few-shot text), and metadata.
    """
    collection = _get_collection()
    if collection is None or collection.count() == 0:
        return []

    embedding = generate_embedding(ocr_text)
    if embedding is None:
        return []

    top_k = top_k or settings.RAG_TOP_K
    min_similarity = min_similarity or settings.RAG_MIN_SIMILARITY

    # Request extra results so we can filter after
    n_results = min(top_k + len(exclude_ids or []) + 2, collection.count())
    if n_results == 0:
        return []

    try:
        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"ChromaDB query failed: {e}")
        return []

    exclude_set = {str(i) for i in (exclude_ids or [])}
    matches: List[Dict[str, Any]] = []

    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    for doc_id, dist, doc, meta in zip(ids, distances, documents, metadatas):
        if doc_id in exclude_set:
            continue

        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        similarity = 1.0 - dist
        if similarity < min_similarity:
            continue

        matches.append({
            "receipt_id": int(doc_id),
            "distance": dist,
            "similarity": round(similarity, 4),
            "document": doc,
            "metadata": meta,
            "is_user_corrected": meta.get("is_user_corrected", False),
        })

        if len(matches) >= top_k:
            break

    # Prioritise user-corrected examples
    matches.sort(key=lambda m: (m["is_user_corrected"], m["similarity"]), reverse=True)
    return matches[:top_k]


def get_store_stats() -> Dict[str, Any]:
    """Return basic stats about the vector store."""
    collection = _get_collection()
    if collection is None:
        return {"status": "unavailable", "count": 0}

    count = collection.count()
    return {
        "status": "ready",
        "count": count,
        "collection": settings.CHROMA_COLLECTION_NAME,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_metadata(fields: Dict[str, Any], is_user_corrected: bool) -> Dict[str, Any]:
    """Flatten extraction fields into ChromaDB-compatible metadata."""
    meta: Dict[str, Any] = {
        "is_user_corrected": is_user_corrected,
    }

    simple_keys = [
        "merchant_name", "date", "currency", "payment_method",
    ]
    for k in simple_keys:
        v = fields.get(k)
        if v is not None:
            meta[k] = str(v)

    numeric_keys = [
        "total_amount", "tax_amount", "subtotal", "vat_percentage_effective",
    ]
    for k in numeric_keys:
        v = fields.get(k)
        if v is not None:
            try:
                meta[k] = float(v)
            except (ValueError, TypeError):
                pass

    # Store items count for quick filtering
    items = fields.get("items")
    if isinstance(items, list):
        meta["items_count"] = len(items)

    return meta


def _build_document_text(ocr_text: str, fields: Dict[str, Any]) -> str:
    """
    Build the document text stored alongside the embedding.

    Format: OCR_TEXT + separator + JSON extraction result.
    This is what gets injected into the LLM prompt as a few-shot example.
    """
    # Keep a trimmed version of OCR text to stay within reasonable size
    trimmed_ocr = ocr_text.strip()[:2000]

    # Build a clean extraction dict (drop internal keys)
    clean_fields = {
        k: v for k, v in fields.items()
        if not k.startswith("_") and v is not None
    }

    extraction_json = json.dumps(clean_fields, indent=2, default=str)

    return f"OCR_TEXT:\n{trimmed_ocr}\n\n---EXTRACTED_JSON---\n{extraction_json}"
