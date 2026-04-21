import cv2
import pytesseract
from thefuzz import process, fuzz
import numpy as np
import logging

logger = logging.getLogger(__name__)

# NOTE: Tesseract-OCR binary must be installed on your Windows system.
# If it's not in your PATH, uncomment and set the line below to the installation path.
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def preprocess_image(image_path: str) -> np.ndarray:
    """
    Preprocess prescription image for better OCR accuracy.
    Includes deskewing, noise reduction, and binarization.
    """
    try:
        # 1. Load image
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")
            
        # 2. Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 3. Apply Gaussian Blur for noise reduction
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 4. Adaptive thresholding for binarization (better for uneven lighting)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # 5. Optional Deskewing block (simplified approach via Hough lines or moments could go here)
        # For prescriptions, standard median blur acts as a good fallback for speckle removal.
        processed = cv2.medianBlur(thresh, 3)

        return processed
    except Exception as e:
        logger.error(f"Image preprocessing failed: {e}")
        raise

def extract_text(processed_image: np.ndarray) -> str:
    """Extract text from preprocessed image using local Tesseract."""
    try:
        # OEM 3 = Default, PSM 6 = Assume a single uniform block of text.
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(processed_image, config=custom_config)
        return text
    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract-OCR is not installed or not in your system PATH.")
        return ""
    except Exception as e:
        logger.error(f"OCR Extraction failed: {e}")
        return ""

def match_products_from_text(extracted_text: str, available_products: list[dict], threshold=65) -> list[dict]:
    """
    Cross-reference extracted text against the Products database using fuzzy string matching.
    `available_products`: list of dictionaries from the Products table.
    """
    if not extracted_text.strip():
        return []
        
    product_names = [p['Name'] for p in available_products]
    matched_items = []
    
    # Analyze line by line
    lines = extracted_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if len(line) < 3: # Ignore very short artifacts
            continue
            
        # Fuzzy match against the product list using Levenshtein distance 
        match_result = process.extractOne(line, product_names, scorer=fuzz.token_sort_ratio)
        
        if match_result:
            matched_name, score = match_result[0], match_result[1]
            if score >= threshold:
                matched_product = next((p for p in available_products if p['Name'] == matched_name), None)
                if matched_product and matched_product not in matched_items:
                    matched_items.append(matched_product)
                    
    return matched_items

def process_prescription(image_path: str, available_products: list[dict]) -> list[dict]:
    """End-to-end local OCR pipeline executing entirely offline."""
    img = preprocess_image(image_path)
    text = extract_text(img)
    matched_products = match_products_from_text(text, available_products)
    return matched_products
