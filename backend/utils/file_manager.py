"""
File management utilities.
"""
import uuid
import shutil
from pathlib import Path
from typing import Optional
from config import settings


def generate_file_id() -> str:
    """Generate a unique file ID."""
    return str(uuid.uuid4())


def save_uploaded_file(file_content: bytes, original_filename: str) -> tuple[str, Path]:
    """
    Save uploaded file to temp directory.
    
    Returns:
        tuple: (file_id, file_path)
    """
    file_id = generate_file_id()
    file_extension = Path(original_filename).suffix
    filename = f"{file_id}{file_extension}"
    file_path = settings.TEMP_DIR / filename
    
    # Write file
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    return file_id, file_path


def get_file_path(file_id: str) -> Optional[Path]:
    """Get file path by file_id."""
    # Search in temp directory
    for file_path in settings.TEMP_DIR.glob(f"{file_id}.*"):
        if file_path.is_file():
            return file_path
    return None


def delete_file(file_path: Path) -> bool:
    """Delete a file if it exists."""
    try:
        if file_path.exists():
            file_path.unlink()
            return True
    except Exception:
        pass
    return False


def cleanup_temp_files(file_id: str) -> None:
    """Clean up all temporary files associated with a file_id."""
    for file_path in settings.TEMP_DIR.glob(f"{file_id}*"):
        if file_path.is_file():
            delete_file(file_path)


def ensure_export_dir() -> Path:
    """Ensure exports directory exists."""
    settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return settings.EXPORTS_DIR

