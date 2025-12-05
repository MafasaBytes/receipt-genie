"""
Classical computer vision-based receipt detection service.
Designed for faint, greyish, low-contrast Dutch receipts on A4 pages.
"""
from pathlib import Path
from typing import List
import cv2
import numpy as np
import logging
from config import settings

logger = logging.getLogger(__name__)


def detect_receipts(image_path: Path) -> List[str]:
    """
    Detect and extract receipts from an image using classical CV techniques.
    
    Designed for faint, greyish, low-contrast receipts on A4 pages.
    Uses contour detection with perspective correction.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        List of paths to cropped receipt images.
        If no receipt is detected, returns [image_path] as fallback.
    """
    try:
        # Step 1: Load image
        img = cv2.imread(str(image_path))
        if img is None:
            logger.warning(f"Could not load image: {image_path}")
            return [str(image_path)]  # Fallback to original
        
        original_img = img.copy()
        height, width = img.shape[:2]
        logger.debug(f"Processing image: {width}x{height}")
        
        # Step 2: Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Step 3: Apply Gaussian blur
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Step 4: Adaptive threshold
        thresh = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 51, 7
        )
        
        # Step 5: Morphology close to highlight borders
        kernel = np.ones((5, 5), np.uint8)
        morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Step 6: Canny edge detection
        edges = cv2.Canny(morph, 50, 200)
        
        # Step 7: Find external contours
        contours, _ = cv2.findContours(
            edges, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            logger.warning(f"No contours found in {image_path}, using fallback")
            return [str(image_path)]
        
        # Step 8: Filter contours by area and aspect ratio
        image_area = height * width
        valid_contours = []
        rejected_contours = []
        total_contours = len(contours)
        
        logger.info(f"Found {total_contours} total contours in image")
        
        for contour in contours:
            # Calculate area ratio
            contour_area = cv2.contourArea(contour)
            area_ratio = contour_area / image_area
            
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = h / w if w > 0 else 0
            
            # Filter criteria:
            # - Area between 2% and 95% of image (relaxed for multiple receipts per page)
            #   (2% allows for smaller receipts when multiple are present)
            # - Tall shape: height > width (aspect ratio > 1.0, relaxed from 1.5)
            #   OR reasonable size (for receipts that might be rotated or square-ish)
            
            rejection_reason = None
            if area_ratio <= 0.02:
                rejection_reason = f"too small (area={area_ratio*100:.2f}% < 2%)"
            elif area_ratio >= 0.95:
                rejection_reason = f"too large (area={area_ratio*100:.2f}% > 95%)"
            elif aspect_ratio <= 1.0 and area_ratio <= 0.1:
                rejection_reason = f"wrong aspect ratio (h/w={aspect_ratio:.2f}, area={area_ratio*100:.2f}%)"
            
            if rejection_reason:
                rejected_contours.append((contour, area_ratio, aspect_ratio, rejection_reason))
            else:
                valid_contours.append((contour, contour_area, x, y, w, h))
                logger.debug(f"Valid contour: area={area_ratio*100:.2f}%, aspect={aspect_ratio:.2f}, bbox=({x},{y},{w},{h})")
        
        logger.info(f"Contour filtering: {len(valid_contours)} valid, {len(rejected_contours)} rejected out of {total_contours} total")
        if rejected_contours and logger.isEnabledFor(logging.DEBUG):
            for idx, (_, area_ratio, aspect_ratio, reason) in enumerate(rejected_contours[:5], 1):  # Log first 5
                logger.debug(f"  Rejected contour {idx}: {reason} (area={area_ratio*100:.2f}%, aspect={aspect_ratio:.2f})")
        
        if not valid_contours:
            logger.warning(f"No valid contours found in {image_path}, using fallback")
            return [str(image_path)]
        
        # Step 9: Sort contours by area (largest first) and filter overlapping ones
        valid_contours.sort(key=lambda x: x[1], reverse=True)  # Sort by area
        
        # Step 10: Filter out overlapping contours (non-maximum suppression)
        # Keep only contours that don't significantly overlap with larger ones
        filtered_contours = []
        overlapping_count = 0
        for i, (contour, area, x, y, w, h) in enumerate(valid_contours):
            # Calculate intersection over union (IoU) with already selected contours
            is_overlapping = False
            for selected_contour, selected_area, sx, sy, sw, sh in filtered_contours:
                # Calculate intersection
                x1 = max(x, sx)
                y1 = max(y, sy)
                x2 = min(x + w, sx + sw)
                y2 = min(y + h, sy + sh)
                
                if x2 > x1 and y2 > y1:
                    intersection = (x2 - x1) * (y2 - y1)
                    union = area + selected_area - intersection
                    iou = intersection / union if union > 0 else 0
                    
                    # If IoU > 0.3, consider it overlapping and skip
                    if iou > 0.3:
                        is_overlapping = True
                        overlapping_count += 1
                        logger.debug(f"Contour {i+1} overlaps with larger contour (IoU={iou:.2f}), skipping")
                        break
            
            if not is_overlapping:
                filtered_contours.append((contour, area, x, y, w, h))
                logger.info(f"Found receipt contour {len(filtered_contours)}: area={area:.0f}, bbox=({x},{y},{w},{h})")
        
        if overlapping_count > 0:
            logger.info(f"Non-maximum suppression: {overlapping_count} overlapping contours removed, {len(filtered_contours)} unique receipts detected")
        
        if not filtered_contours:
            logger.warning(f"No non-overlapping contours found in {image_path}, using fallback")
            return [str(image_path)]
        
        # Step 11: Process each detected receipt contour
        cropped_paths = []
        for receipt_idx, (contour, area, bx, by, bw, bh) in enumerate(filtered_contours):
            try:
                # Approximate contour to polygon
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Get four corner points for perspective transform
                # If we have 4 points, use them; otherwise use bounding box corners
                if len(approx) == 4:
                    # Reorder points to: top-left, top-right, bottom-right, bottom-left
                    pts = approx.reshape(4, 2)
                    rect = order_points(pts)
                else:
                    # Use bounding box corners if approximation doesn't give 4 points
                    logger.debug(f"Receipt {receipt_idx + 1}: Contour approximation didn't yield 4 points, using bounding box")
                    rect = np.array([
                        [bx, by],           # top-left
                        [bx + bw, by],      # top-right
                        [bx + bw, by + bh], # bottom-right
                        [bx, by + bh]       # bottom-left
                    ], dtype=np.float32)
                
                # Calculate dimensions for warped image
                width_a = np.sqrt(((rect[2][0] - rect[3][0]) ** 2) + ((rect[2][1] - rect[3][1]) ** 2))
                width_b = np.sqrt(((rect[1][0] - rect[0][0]) ** 2) + ((rect[1][1] - rect[0][1]) ** 2))
                max_width = max(int(width_a), int(width_b))
                
                height_a = np.sqrt(((rect[1][0] - rect[2][0]) ** 2) + ((rect[1][1] - rect[2][1]) ** 2))
                height_b = np.sqrt(((rect[0][0] - rect[3][0]) ** 2) + ((rect[0][1] - rect[3][1]) ** 2))
                max_height = max(int(height_a), int(height_b))
                
                # Skip if dimensions are too small (likely noise)
                if max_width < 100 or max_height < 100:
                    logger.debug(f"Receipt {receipt_idx + 1}: Dimensions too small ({max_width}x{max_height}), skipping")
                    continue
                
                # Define destination points for perspective transform
                dst = np.array([
                    [0, 0],
                    [max_width - 1, 0],
                    [max_width - 1, max_height - 1],
                    [0, max_height - 1]
                ], dtype=np.float32)
                
                # Get perspective transform matrix and warp
                M = cv2.getPerspectiveTransform(rect, dst)
                warped = cv2.warpPerspective(original_img, M, (max_width, max_height))
                
                # Save cropped receipt with index
                output_path = image_path.parent / f"{image_path.stem}_receipt_{receipt_idx + 1}_cropped.png"
                cv2.imwrite(str(output_path), warped)
                logger.info(f"Saved cropped receipt {receipt_idx + 1} to: {output_path}")
                cropped_paths.append(str(output_path))
                
            except Exception as e:
                logger.error(f"Error processing receipt contour {receipt_idx + 1}: {str(e)}")
                logger.exception("Contour processing error details:")
                continue
        
        if not cropped_paths:
            logger.warning(f"Failed to process any receipts from {image_path}, using fallback")
            return [str(image_path)]
        
        logger.info(f"Successfully detected and cropped {len(cropped_paths)} receipt(s) from {image_path}")
        return cropped_paths
        
    except Exception as e:
        logger.error(f"Error in receipt detection: {str(e)}")
        logger.exception("Full traceback:")
        # Fallback: return original image path
        return [str(image_path)]


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
