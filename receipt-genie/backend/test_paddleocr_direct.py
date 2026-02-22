"""
Direct test of PaddleOCR to see what it returns.
"""
import sys
from pathlib import Path
from paddleocr import PaddleOCR
import json

image_path = sys.argv[1] if len(sys.argv) > 1 else "temp/crops/67465225-3e72-41fe-90ce-d051dd53a4e4_page_6_region_60_622beefe.png"

print("=" * 60)
print("Direct PaddleOCR Test")
print("=" * 60)
print(f"Image: {image_path}")
print()

# Initialize PaddleOCR
print("Initializing PaddleOCR...")
ocr = PaddleOCR(use_angle_cls=True, lang='en')
print("PaddleOCR initialized")
print()

# Run OCR
print("Running OCR...")
result = ocr.ocr(str(image_path))
print()

# Inspect result
print("=" * 60)
print("RESULT INSPECTION")
print("=" * 60)
print(f"Result type: {type(result)}")
print(f"Result is None: {result is None}")
if result is not None:
    print(f"Result length: {len(result)}")
    if len(result) > 0:
        print(f"Result[0] type: {type(result[0])}")
        print(f"Result[0] is None: {result[0] is None}")
        
        if result[0] is not None:
            if isinstance(result[0], dict):
                print(f"Result[0] is dict with keys: {list(result[0].keys())}")
                for key in result[0].keys():
                    value = result[0][key]
                    print(f"  {key}: {type(value)}, length: {len(value) if hasattr(value, '__len__') else 'N/A'}")
                    if isinstance(value, list) and len(value) > 0:
                        print(f"    First item: {value[0]}")
            elif isinstance(result[0], (list, tuple)):
                print(f"Result[0] is list/tuple with {len(result[0])} items")
                if len(result[0]) > 0:
                    print(f"Result[0][0] type: {type(result[0][0])}")
                    print(f"Result[0][0] content: {result[0][0]}")
                    if isinstance(result[0][0], (list, tuple)) and len(result[0][0]) > 1:
                        print(f"Result[0][0][1] (text info): {result[0][0][1]}")
            
            print(f"\nFull result[0] (first 1000 chars):")
            print(str(result[0])[:1000])
        
        # Try to extract text manually
        print("\n" + "=" * 60)
        print("MANUAL TEXT EXTRACTION ATTEMPT")
        print("=" * 60)
        
        extracted = None
        
        # Method 1: Check if it's a dict with rec_texts
        if isinstance(result[0], dict):
            if 'rec_texts' in result[0]:
                rec_texts = result[0]['rec_texts']
                print(f"Found rec_texts: {type(rec_texts)}, length: {len(rec_texts) if isinstance(rec_texts, list) else 'N/A'}")
                if isinstance(rec_texts, list):
                    extracted = '\n'.join(str(t) for t in rec_texts if t)
                    print(f"Extracted from rec_texts: {len(extracted)} chars")
        
        # Method 2: Check if it's a list of tuples
        if not extracted and isinstance(result[0], (list, tuple)):
            text_lines = []
            for item in result[0]:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    text_info = item[1]
                    if isinstance(text_info, (list, tuple)) and len(text_info) > 0:
                        text_lines.append(str(text_info[0]))
            if text_lines:
                extracted = '\n'.join(text_lines)
                print(f"Extracted from list format: {len(extracted)} chars, {len(text_lines)} lines")
        
        if extracted:
            print(f"\nEXTRACTED TEXT ({len(extracted)} chars):")
            print("-" * 60)
            print(extracted[:500])
            print("-" * 60)
        else:
            print("NO TEXT EXTRACTED")
    else:
        print("Result is empty list")
else:
    print("Result is None")

