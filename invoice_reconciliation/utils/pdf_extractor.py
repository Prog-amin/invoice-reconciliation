"""PDF and image text extraction utilities."""

import os
import re
from pathlib import Path
from typing import Tuple

import pytesseract
from PIL import Image
import pypdf

# Try to import pdf2image, but handle if poppler is not installed
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

# Try to import OpenCV for image preprocessing
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from ..config import TESSERACT_CMD, POPPLER_PATH

# Configure Tesseract path
if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


class PDFExtractor:
    """Extract text from PDF and image files."""
    
    def __init__(self):
        """Initialize the PDF extractor."""
        self.tesseract_available = self._check_tesseract()
    
    def _check_tesseract(self) -> bool:
        """Check if Tesseract is available."""
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
    
    def extract_text(self, file_path: str) -> Tuple[str, float, str]:
        """
        Extract text from a PDF or image file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (extracted_text, confidence_score, document_quality)
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        suffix = file_path.suffix.lower()
        
        if suffix == ".pdf":
            return self._extract_from_pdf(file_path)
        elif suffix in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
            return self._extract_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")
    
    def _extract_from_pdf(self, file_path: Path) -> Tuple[str, float, str]:
        """Extract text from a PDF file."""
        text = ""
        confidence = 0.95
        quality = "excellent"
        
        # First, try direct text extraction (for clean PDFs)
        try:
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"Direct PDF extraction failed: {e}")
        
        # If we got significant text, it's a clean PDF
        if len(text.strip()) > 100:
            # Check if text looks reasonable (not garbled)
            if self._is_text_quality_good(text):
                return text.strip(), 0.95, "excellent"
        
        # Fall back to OCR for scanned PDFs
        if PDF2IMAGE_AVAILABLE and self.tesseract_available:
            try:
                ocr_text, ocr_confidence = self._ocr_pdf(file_path)
                if len(ocr_text.strip()) > len(text.strip()):
                    # Determine quality based on OCR confidence
                    if ocr_confidence >= 0.85:
                        quality = "good"
                    elif ocr_confidence >= 0.70:
                        quality = "acceptable"
                    else:
                        quality = "poor"
                    return ocr_text.strip(), ocr_confidence, quality
            except Exception as e:
                print(f"OCR extraction failed: {e}")
        
        # Return whatever we have
        if len(text.strip()) > 0:
            return text.strip(), 0.75, "acceptable"
        
        return "", 0.0, "unreadable"
    
    def _ocr_pdf(self, file_path: Path) -> Tuple[str, float]:
        """OCR a PDF file by converting to images first."""
        images = convert_from_path(
            str(file_path),
            poppler_path=POPPLER_PATH if POPPLER_PATH else None,
            dpi=300  # Higher DPI for better OCR
        )
        
        all_text = []
        total_confidence = 0.0
        
        for img in images:
            # Preprocess image if OpenCV is available
            if CV2_AVAILABLE:
                img = self._preprocess_image(img)
            
            # Get detailed OCR data including confidence
            data = pytesseract.image_to_data(
                img, 
                output_type=pytesseract.Output.DICT,
                config='--oem 3 --psm 6'
            )
            
            # Extract text and calculate confidence
            page_text = []
            page_confidences = []
            
            for i, text in enumerate(data['text']):
                if text.strip():
                    page_text.append(text)
                    conf = int(data['conf'][i])
                    if conf > 0:  # -1 means no confidence available
                        page_confidences.append(conf / 100.0)
            
            all_text.append(' '.join(page_text))
            if page_confidences:
                total_confidence += sum(page_confidences) / len(page_confidences)
        
        text = '\n'.join(all_text)
        avg_confidence = total_confidence / len(images) if images else 0.0
        
        return text, avg_confidence
    
    def _extract_from_image(self, file_path: Path) -> Tuple[str, float, str]:
        """Extract text from an image file using OCR."""
        if not self.tesseract_available:
            raise RuntimeError("Tesseract OCR is not available")
        
        img = Image.open(file_path)
        
        # Preprocess if OpenCV is available
        if CV2_AVAILABLE:
            img = self._preprocess_image(img)
        
        # Get detailed OCR data
        data = pytesseract.image_to_data(
            img,
            output_type=pytesseract.Output.DICT,
            config='--oem 3 --psm 6'
        )
        
        text_parts = []
        confidences = []
        
        for i, text in enumerate(data['text']):
            if text.strip():
                text_parts.append(text)
                conf = int(data['conf'][i])
                if conf > 0:
                    confidences.append(conf / 100.0)
        
        text = ' '.join(text_parts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        # Determine quality
        if avg_confidence >= 0.90:
            quality = "excellent"
        elif avg_confidence >= 0.80:
            quality = "good"
        elif avg_confidence >= 0.65:
            quality = "acceptable"
        else:
            quality = "poor"
        
        return text, avg_confidence, quality
    
    def _preprocess_image(self, img) -> Image.Image:
        """Preprocess image for better OCR results."""
        # Convert PIL Image to numpy array
        if isinstance(img, Image.Image):
            img_array = np.array(img)
        else:
            img_array = img
        
        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Deskew the image
        gray = self._deskew(gray)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
        
        return Image.fromarray(denoised)
    
    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """Deskew a rotated image."""
        # Find all edges
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        
        # Detect lines using Hough transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        
        if lines is not None:
            angles = []
            for line in lines[:20]:  # Consider first 20 lines
                rho, theta = line[0]
                angle = np.degrees(theta) - 90
                if -45 < angle < 45:  # Only consider reasonable angles
                    angles.append(angle)
            
            if angles:
                median_angle = np.median(angles)
                if abs(median_angle) > 0.5:  # Only rotate if significant
                    # Rotate the image
                    (h, w) = image.shape[:2]
                    center = (w // 2, h // 2)
                    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                    rotated = cv2.warpAffine(
                        image, M, (w, h),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE
                    )
                    return rotated
        
        return image
    
    def _is_text_quality_good(self, text: str) -> bool:
        """Check if extracted text appears to be of good quality."""
        if not text:
            return False
        
        # Check for reasonable word patterns
        words = text.split()
        if len(words) < 10:
            return False
        
        # Check ratio of recognizable vs garbled text
        recognizable = sum(
            1 for w in words 
            if re.match(r'^[a-zA-Z0-9£$€.,\-:]+$', w)
        )
        
        return recognizable / len(words) > 0.7
