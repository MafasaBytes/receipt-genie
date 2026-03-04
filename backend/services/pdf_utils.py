"""
PDF processing utilities using pypdfium2.
"""
from pathlib import Path
from typing import List
import pypdfium2 as pdfium
from PIL import Image
import io


def pdf_to_images(pdf_path: Path, output_dir: Path) -> List[Path]:
    """
    Convert PDF pages to images.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save images
        
    Returns:
        List of paths to generated images
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths = []
    
    try:
        # Open PDF
        pdf = pdfium.PdfDocument(str(pdf_path))
        
        # Convert each page to image
        for page_num in range(len(pdf)):
            page = pdf.get_page(page_num)
            
            # Render page to image (300 DPI for good quality)
            bitmap = page.render(scale=300/72)  # 72 is default DPI
            pil_image = bitmap.to_pil()
            
            # Save image
            image_filename = f"{pdf_path.stem}_page_{page_num + 1}.png"
            image_path = output_dir / image_filename
            pil_image.save(image_path, "PNG")
            image_paths.append(image_path)
            
            # Clean up
            bitmap.close()
            page.close()
        
        pdf.close()
        
    except Exception as e:
        raise Exception(f"Error converting PDF to images: {str(e)}")
    
    return image_paths


def get_pdf_page_count(pdf_path: Path) -> int:
    """Get the number of pages in a PDF."""
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        count = len(pdf)
        pdf.close()
        return count
    except Exception:
        return 0

