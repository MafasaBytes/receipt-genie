"""
Advanced classical computer vision-based receipt detection service.
Designed for faint, greyish, low-contrast Dutch receipts with auto-deskew,
orientation correction, and multi-receipt slicing.
"""
from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np
import logging
import uuid
from config import settings

logger = logging.getLogger(__name__)


def detect_receipts(image_path: Path) -> List[str]:
    """
    Detect and extract receipts from an image using advanced CV techniques.
    
    Features:
    - Auto-deskew
    - Brightness/contrast normalization
    - Edge-boost filtering
    - Automatic orientation correction
    - Multi-receipt slicing for stacked receipts
    - Robust detection for faint, low-contrast receipts
    
    Args:
        image_path: Path to the image file
        
    Returns:
        List of paths to cropped receipt images.
        If no receipt is detected, returns [image_path] as fallback.
    """
    try:
        # Step 1: Load & Preprocess
        logger.info(f"Loading image: {image_path}")
        img = cv2.imread(str(image_path))
        if img is None:
            logger.warning(f"Could not load image: {image_path}")
            return [str(image_path)]
        
        original_img = img.copy()
        height, width = img.shape[:2]
        logger.debug(f"Original image size: {width}x{height}")
        
        # Preprocess image
        preprocessed = preprocess_image(img)
        
        # Step 2: Auto-deskew
        logger.debug("Applying auto-deskew...")
        deskewed = deskew(preprocessed)
        
        # Step 3: Orientation correction
        logger.debug("Fixing orientation...")
        oriented = fix_orientation(deskewed)
        
        # Step 4: Extract contours for stacked receipts
        logger.info("=" * 60)
        logger.info("EXTRACTING CONTOURS")
        logger.info("=" * 60)
        contours = extract_contours(oriented)
        
        if not contours:
            logger.warning(f"No contours found in {image_path}, using fallback")
            return [str(image_path)]
        
        logger.info(f"Found {len(contours)} potential receipt regions after filtering")
        
        # Step 5: Multi-receipt slicing and cropping
        crops_dir = settings.TEMP_DIR / "crops"
        crops_dir.mkdir(parents=True, exist_ok=True)
        
        cropped_paths = []
        rejected_regions = []
        
        # Sort contours by Y-coordinate (top to bottom)
        sorted_contours = sort_contours_by_position(contours, oriented.shape[:2])
        
        logger.info("=" * 60)
        logger.info("PROCESSING CONTOURS")
        logger.info("=" * 60)
        
        for idx, contour in enumerate(sorted_contours):
            try:
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                img_area = oriented.shape[0] * oriented.shape[1]
                contour_area = cv2.contourArea(contour)
                area_ratio = contour_area / img_area
                
                logger.info(f"Processing contour {idx + 1}/{len(sorted_contours)}: bbox=({x},{y},{w},{h}), area={area_ratio*100:.2f}%")
                
                # Additional filtering (very relaxed criteria for faint receipts)
                if area_ratio < 0.002:  # 0.2% minimum area (very relaxed)
                    reason = f"area ratio too small ({area_ratio*100:.2f}% < 0.2%)"
                    logger.warning(f"  REJECTED: {reason}")
                    rejected_regions.append({"contour": idx + 1, "reason": reason, "area_ratio": area_ratio})
                    continue
                
                if area_ratio > 0.95:
                    reason = f"area ratio too large ({area_ratio*100:.2f}% > 95%)"
                    logger.warning(f"  REJECTED: {reason}")
                    rejected_regions.append({"contour": idx + 1, "reason": reason, "area_ratio": area_ratio})
                    continue
                
                # Extract region
                region = oriented[y:y+h, x:x+w]
                
                if region.size == 0:
                    reason = "extracted region is empty"
                    logger.warning(f"  REJECTED: {reason}")
                    rejected_regions.append({"contour": idx + 1, "reason": reason})
                    continue
                
                # Check if region needs slicing (covers > 70% of page height - relaxed from 80%)
                if h > oriented.shape[0] * 0.70:
                    logger.info(f"  Large region detected ({h}px height, {h/oriented.shape[0]*100:.1f}% of page), attempting slicing...")
                    slices = slice_receipt_region(region)
                    
                    if len(slices) == 0:
                        reason = "slicing produced no valid slices"
                        logger.warning(f"  REJECTED: {reason}")
                        rejected_regions.append({"contour": idx + 1, "reason": reason})
                        continue
                    
                    logger.info(f"  Sliced into {len(slices)} receipt(s)")
                    for slice_idx, slice_img in enumerate(slices):
                        if slice_img.size > 0:
                            crop_path = save_crop(slice_img, crops_dir, f"{image_path.stem}_region_{idx}_slice_{slice_idx}")
                            cropped_paths.append(crop_path)
                            logger.info(f"  ✓ Saved slice {slice_idx + 1}/{len(slices)}: {Path(crop_path).name}")
                        else:
                            logger.warning(f"  REJECTED slice {slice_idx + 1}: empty slice")
                else:
                    # Single receipt in this region
                    crop_path = save_crop(region, crops_dir, f"{image_path.stem}_region_{idx}")
                    cropped_paths.append(crop_path)
                    logger.info(f"  ✓ Saved receipt: {Path(crop_path).name}")
                    
            except Exception as e:
                reason = f"processing error: {str(e)}"
                logger.error(f"  REJECTED contour {idx + 1}: {reason}")
                logger.exception("Error details:")
                rejected_regions.append({"contour": idx + 1, "reason": reason})
                continue
        
        # Summary logging
        logger.info("=" * 60)
        logger.info("DETECTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total contours processed: {len(sorted_contours)}")
        logger.info(f"Successfully extracted: {len(cropped_paths)} receipt(s)")
        logger.info(f"Rejected regions: {len(rejected_regions)}")
        
        if rejected_regions:
            logger.warning("Rejected regions details:")
            rejection_reasons_summary = {}
            for r in rejected_regions:
                reason_type = r["reason"].split(":")[0] if ":" in r["reason"] else r["reason"]
                rejection_reasons_summary[reason_type] = rejection_reasons_summary.get(reason_type, 0) + 1
                logger.warning(f"  Contour {r['contour']}: {r['reason']}")
            
            logger.warning(f"Rejection summary: {rejection_reasons_summary}")
        
        logger.info("=" * 60)
        
        if not cropped_paths:
            logger.warning(f"No valid receipts extracted from {image_path}, using fallback")
            return [str(image_path)]
        
        logger.info(f"Successfully extracted {len(cropped_paths)} receipt(s) from {image_path}")
        return cropped_paths
        
    except Exception as e:
        logger.error(f"Error in receipt detection: {str(e)}")
        logger.exception("Full traceback:")
        return [str(image_path)]


def preprocess_image(img: np.ndarray) -> np.ndarray:
    """
    Step 1: Load & Preprocess
    - Convert to grayscale
    - Apply CLAHE for brightness normalization
    - Apply contrast stretching
    - Apply edge-boost filter
    """
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    equalized = clahe.apply(gray)
    
    # Normalize contrast
    normalized = cv2.normalize(equalized, None, 0, 255, cv2.NORM_MINMAX)
    
    # Apply edge-boost filter
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]], dtype=np.float32)
    edge_boosted = cv2.filter2D(normalized, -1, kernel)
    
    # Clip values to valid range
    edge_boosted = np.clip(edge_boosted, 0, 255).astype(np.uint8)
    
    return edge_boosted


def deskew(image: np.ndarray) -> np.ndarray:
    """
    Step 2: Auto-deskew using HoughLines-based angle estimation.
    
    Detects rotation angle and rotates image to correct skew.
    """
    # Apply Canny edge detection
    edges = cv2.Canny(image, 50, 200, apertureSize=3)
    
    # Detect lines using HoughLines
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    
    if lines is None or len(lines) == 0:
        logger.debug("No lines detected for deskew, returning original")
        return image
    
    # Calculate angles
    angles = []
    for line in lines:
        rho, theta = line[0]
        # Convert to degrees
        angle = np.degrees(theta) - 90
        # Filter out near-vertical lines (they don't indicate skew)
        if abs(angle) < 45:
            angles.append(angle)
    
    if not angles:
        logger.debug("No valid angles found for deskew")
        return image
    
    # Compute median angle (more robust than mean)
    median_angle = np.median(angles)
    
    # Only deskew if angle is significant (> 2 degrees)
    if abs(median_angle) > 2:
        logger.info(f"Deskewing image by {median_angle:.2f} degrees")
        
        # Get rotation matrix
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        
        # Calculate new dimensions
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        
        # Adjust rotation matrix for new dimensions
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        
        # Rotate image
        deskewed = cv2.warpAffine(image, M, (new_w, new_h), 
                                  flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
        return deskewed
    
    logger.debug(f"Skew angle {median_angle:.2f} degrees is acceptable, skipping deskew")
    return image


def fix_orientation(image: np.ndarray) -> np.ndarray:
    """
    Step 3: Orientation correction.
    
    Ensures receipt is portrait-oriented (height > width).
    Uses text density analysis for better detection.
    """
    h, w = image.shape[:2]
    
    # Initial check: if landscape, rotate
    if h < w * 0.8:
        logger.debug("Image appears landscape, rotating 90° clockwise")
        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        h, w = image.shape[:2]
    
    # Text density check using horizontal projection
    # Receipts typically have more text density in horizontal direction
    horizontal_projection = cv2.reduce(image, 1, cv2.REDUCE_SUM, dtype=cv2.CV_32F)
    vertical_projection = cv2.reduce(image, 0, cv2.REDUCE_SUM, dtype=cv2.CV_32F)
    
    # Calculate variance (text density indicator)
    h_variance = np.var(horizontal_projection)
    v_variance = np.var(vertical_projection)
    
    # If vertical variance is much higher, might be rotated
    if v_variance > h_variance * 1.5 and h < w:
        logger.debug("Text density suggests rotation needed")
        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        h, w = image.shape[:2]
    
    # Final check: ensure portrait orientation
    if h <= w:
        logger.debug("Final orientation check: rotating to portrait")
        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    
    return image


def extract_contours(image: np.ndarray) -> List[np.ndarray]:
    """
    Step 4: Extract contours for stacked receipts.
    
    Uses aggressive thresholding and morphology to detect receipt boundaries.
    """
    # Adaptive threshold
    thresh = cv2.adaptiveThreshold(
        image,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        35,
        10
    )
    
    # Morphology: close with tall kernel for vertically stacked receipts
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 45))
    morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # Additional opening to remove noise
    kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel_small)
    
    # Canny edge detection
    edges = cv2.Canny(morph, 40, 160)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        logger.warning("No contours found after edge detection")
        return []
    
    logger.info(f"Found {len(contours)} total contours from edge detection")
    
    # Filter contours by size and aspect ratio
    h, w = image.shape[:2]
    valid_contours = []
    rejected_contours = []
    
    logger.info(f"Evaluating {len(contours)} contours for receipt detection (image size: {w}x{h})")
    
    # Very relaxed thresholds for faint receipts
    # Use scoring system: accept if meets at least 1 out of 4 criteria OR has reasonable area
    min_height_ratio = 0.01   # 1% of image height
    min_width_ratio = 0.03    # 3% of image width
    min_aspect_ratio = 0.3    # Very permissive aspect ratio
    min_area_ratio = 0.001    # 0.1% of image area (very relaxed)
    
    for idx, contour in enumerate(contours):
            x, y, cw, ch = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            area_ratio = area / (h * w)
            aspect_ratio = ch / cw if cw > 0 else 0
            
            rejection_reasons = []
            score = 0  # Score based on how many criteria are met
            
            # Check each criterion and score
            if ch > h * min_height_ratio:
                score += 1
            else:
                rejection_reasons.append(f"height too small ({ch}px < {h*min_height_ratio:.0f}px, {ch/h*100:.1f}% < {min_height_ratio*100:.0f}%)")
            
            if cw > w * min_width_ratio:
                score += 1
            else:
                rejection_reasons.append(f"width too small ({cw}px < {w*min_width_ratio:.0f}px, {cw/w*100:.1f}% < {min_width_ratio*100:.0f}%)")
            
            if aspect_ratio > min_aspect_ratio:
                score += 1
            else:
                rejection_reasons.append(f"aspect ratio too low ({aspect_ratio:.2f} < {min_aspect_ratio:.2f})")
            
            if area_ratio > min_area_ratio:
                score += 1
            else:
                rejection_reasons.append(f"area too small ({area_ratio*100:.2f}% < {min_area_ratio*100:.2f}%)")
            
            # Reject if area is too large (full page)
            if area_ratio > 0.95:
                rejection_reasons.append(f"area too large ({area_ratio*100:.2f}% > 95%)")
                score = 0
            
            # Accept if: score >= 1 OR area_ratio > 0.0005 (very permissive)
            # This allows small receipts that might fail some criteria
            # Also accept if it's reasonably sized (height > 50px and width > 50px)
            is_reasonably_sized = ch > 50 and cw > 50
            
            if score >= 1 or area_ratio > 0.0005 or is_reasonably_sized:
                valid_contours.append(contour)
                accept_reason = []
                if score >= 1:
                    accept_reason.append(f"score={score}/4")
                if area_ratio > 0.0005:
                    accept_reason.append(f"area={area_ratio*100:.2f}%")
                if is_reasonably_sized:
                    accept_reason.append(f"size={cw}x{ch}px")
                logger.info(f"Contour {idx + 1} ACCEPTED ({', '.join(accept_reason)}): bbox=({x},{y},{cw},{ch}), area={area_ratio*100:.2f}%, aspect={aspect_ratio:.2f}")
            else:
                rejected_contours.append({
                    "index": idx + 1,
                    "bbox": (x, y, cw, ch),
                    "area_ratio": area_ratio,
                    "aspect_ratio": aspect_ratio,
                    "score": score,
                    "reasons": rejection_reasons
                })
                logger.warning(f"Contour {idx + 1} REJECTED (score={score}/4): {', '.join(rejection_reasons)} (bbox=({x},{y},{cw},{ch}), area={area_ratio*100:.2f}%, aspect={aspect_ratio:.2f})")
    
    logger.info(f"Contour filtering results: {len(valid_contours)} ACCEPTED, {len(rejected_contours)} REJECTED out of {len(contours)} total")
    
    # Log summary of rejection reasons
    if rejected_contours:
        rejection_summary = {}
        for r in rejected_contours:
            for reason in r["reasons"]:
                reason_type = reason.split(":")[0] if ":" in reason else reason
                rejection_summary[reason_type] = rejection_summary.get(reason_type, 0) + 1
        
        logger.warning(f"Rejection reasons summary: {rejection_summary}")
        
        # Log rejected contours with scores
        logger.warning(f"Rejected contours breakdown:")
        for r in rejected_contours[:20]:  # Show first 20
            score_info = f"score={r.get('score', 'N/A')}/4" if 'score' in r else ""
            logger.warning(f"  Contour {r['index']} ({score_info}): {', '.join(r['reasons'][:2])}")  # Show first 2 reasons
        if len(rejected_contours) > 20:
            logger.warning(f"  ... and {len(rejected_contours) - 20} more rejected contours")
    
    return valid_contours


def slice_receipt_region(region: np.ndarray) -> List[np.ndarray]:
    """
    Step 5: Multi-receipt slicing using horizontal projection.
    
    Splits stacked receipts by finding valleys in horizontal projection.
    """
    h, w = region.shape[:2]
    
    # Calculate horizontal projection (sum of pixels along rows)
    horizontal_proj = cv2.reduce(region, 1, cv2.REDUCE_SUM, dtype=cv2.CV_32F)
    horizontal_proj = horizontal_proj.flatten()
    
    # Normalize projection
    if horizontal_proj.max() > 0:
        horizontal_proj = horizontal_proj / horizontal_proj.max()
    
    # Find valleys (gaps between receipts)
    # Use threshold to identify text regions vs gaps
    # Lower threshold (0.2 instead of 0.3) to catch faint receipts
    threshold = np.mean(horizontal_proj) * 0.2  # 20% of mean as threshold
    
    # Find continuous regions above threshold
    above_threshold = horizontal_proj > threshold
    
    # Find split points (transitions from text to gap)
    splits = []
    in_text = False
    text_start = 0
    
    for i, is_text in enumerate(above_threshold):
        if is_text and not in_text:
            # Entering text region
            if text_start > 0:
                # Save split point (middle of gap)
                splits.append((text_start + i) // 2)
            text_start = i
            in_text = True
        elif not is_text and in_text:
            # Exiting text region
            in_text = False
    
    # If no clear splits found, try alternative method
    if len(splits) == 0:
        # Use simple gradient-based approach (no scipy dependency)
        # Find local minima by checking for valleys
        splits = []
        for i in range(1, len(horizontal_proj) - 1):
            # Check if current point is a valley (lower than neighbors)
            if (horizontal_proj[i] < threshold and 
                horizontal_proj[i] < horizontal_proj[i-1] and
                horizontal_proj[i] < horizontal_proj[i+1]):
                splits.append(i)
        
        # Remove splits that are too close together
        if len(splits) > 1:
            min_distance = h // 10
            filtered_splits = [splits[0]]
            for s in splits[1:]:
                if s - filtered_splits[-1] >= min_distance:
                    filtered_splits.append(s)
            splits = filtered_splits
    
    # Remove splits too close to edges
    splits = [s for s in splits if s > h * 0.05 and s < h * 0.95]
    
    # Create slices
    slices = []
    start = 0
    
    for split in sorted(splits):
        if split - start > h * 0.10:  # Minimum slice height
            slice_img = region[start:split, :]
            if slice_img.size > 0:
                slices.append(slice_img)
            start = split
    
    # Add final slice
    if h - start > h * 0.10:
        slice_img = region[start:, :]
        if slice_img.size > 0:
            slices.append(slice_img)
    
    # If no splits found, return original region as single slice
    if len(slices) == 0:
        logger.debug("No splits found, returning original region")
        return [region]
    
    logger.info(f"Split region into {len(slices)} slices")
    return slices


def sort_contours_by_position(contours: List[np.ndarray], image_shape: Tuple[int, int]) -> List[np.ndarray]:
    """
    Sort contours by Y-coordinate (top to bottom) for consistent processing order.
    """
    # Get bounding boxes
    bounding_boxes = [(cv2.boundingRect(c), c) for c in contours]
    
    # Sort by Y-coordinate (top to bottom)
    sorted_boxes = sorted(bounding_boxes, key=lambda x: x[0][1])
    
    return [contour for _, contour in sorted_boxes]


def save_crop(crop_img: np.ndarray, output_dir: Path, base_name: str) -> str:
    """
    Save cropped receipt image to disk.
    
    Args:
        crop_img: Cropped image array
        output_dir: Directory to save crop
        base_name: Base name for the file
        
    Returns:
        Path to saved crop as string
    """
    # Generate unique filename
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{base_name}_{unique_id}.png"
    crop_path = output_dir / filename
    
    # Save image
    cv2.imwrite(str(crop_path), crop_img)
    
    return str(crop_path)


def order_points(pts):
    """
    Order four points in the order: top-left, top-right, bottom-right, bottom-left.
    
    Args:
        pts: Array of 4 points
        
    Returns:
        Ordered array of points
    """
    # Initialize ordered points
    rect = np.zeros((4, 2), dtype=np.float32)
    
    # Sum and difference will help identify corners
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    
    # Top-left: smallest sum
    rect[0] = pts[np.argmin(s)]
    # Bottom-right: largest sum
    rect[2] = pts[np.argmax(s)]
    
    # Top-right: smallest difference
    rect[1] = pts[np.argmin(diff)]
    # Bottom-left: largest difference
    rect[3] = pts[np.argmax(diff)]
    
    return rect


def crop_receipt(image_path: Path, bbox: tuple) -> Path:
    """
    Legacy function for backward compatibility.
    Now redirects to detect_receipts which handles cropping internally.
    
    Args:
        image_path: Path to the source image
        bbox: Bounding box (x1, y1, x2, y2) - ignored, kept for compatibility
        
    Returns:
        Path to the cropped image
    """
    # Use the new detection function
    cropped_paths = detect_receipts(image_path)
    if cropped_paths:
        return Path(cropped_paths[0])
    return image_path
