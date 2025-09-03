import PyPDF2
import fitz  # PyMuPDF
from typing import List, Dict, Any, Tuple
import structlog
from io import BytesIO
import base64
from PIL import Image

logger = structlog.get_logger()

class PDFService:
    def __init__(self):
        pass
    
    async def extract_text_and_images(self, file_content: bytes) -> Tuple[str, List[Dict[str, Any]]]:
        """Extract text and images from PDF"""
        try:
            # Extract text using PyPDF2
            text_content = await self._extract_text_pypdf2(file_content)
            
            # Extract images and detailed layout using PyMuPDF
            images_and_layout = await self._extract_images_and_layout(file_content)
            
            return text_content, images_and_layout
            
        except Exception as e:
            logger.error("PDF extraction failed", error=str(e))
            raise
    
    async def _extract_text_pypdf2(self, file_content: bytes) -> str:
        """Extract text using PyPDF2"""
        pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
        text_content = ""
        
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            text_content += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
        
        return text_content
    
    async def _extract_images_and_layout(self, file_content: bytes) -> List[Dict[str, Any]]:
        """Extract images and layout information using PyMuPDF"""
        doc = fitz.open(stream=file_content, filetype="pdf")
        pages_data = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_data = {
                "page_number": page_num + 1,
                "text_blocks": [],
                "images": [],
                "tables": []
            }
            
            # Extract text blocks with positioning
            text_dict = page.get_text("dict")
            for block in text_dict["blocks"]:
                if "lines" in block:
                    block_text = ""
                    for line in block["lines"]:
                        for span in line["spans"]:
                            block_text += span["text"] + " "
                    
                    if block_text.strip():
                        page_data["text_blocks"].append({
                            "text": block_text.strip(),
                            "bbox": block["bbox"],  # [x0, y0, x1, y1]
                            "font_size": line["spans"][0]["size"] if line["spans"] else 12
                        })
            
            # Extract images
            image_list = page.get_images()
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        img_data = pix.tobytes("png")
                        img_base64 = base64.b64encode(img_data).decode()
                        
                        page_data["images"].append({
                            "index": img_index,
                            "data": img_base64,
                            "format": "png",
                            "bbox": page.get_image_bbox(img)
                        })
                    
                    pix = None
                    
                except Exception as e:
                    logger.warning("Failed to extract image", page=page_num, image=img_index, error=str(e))
            
            # Extract tables using simple heuristics
            tables = self._extract_tables_from_page(page)
            page_data["tables"] = tables
            
            pages_data.append(page_data)
        
        doc.close()
        return pages_data
    
    def _extract_tables_from_page(self, page) -> List[Dict[str, Any]]:
        """Extract tables using text positioning heuristics"""
        text_dict = page.get_text("dict")
        tables = []
        
        # Simple table detection based on aligned text blocks
        # This is a basic implementation - could be enhanced with more sophisticated table detection
        
        potential_table_blocks = []
        for block in text_dict["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        line_text += span["text"] + " "
                    
                    # Look for lines that might be table rows (contain numbers, separated by spaces/tabs)
                    if self._looks_like_table_row(line_text.strip()):
                        potential_table_blocks.append({
                            "text": line_text.strip(),
                            "bbox": line["bbox"],
                            "y_position": line["bbox"][1]
                        })
        
        if potential_table_blocks:
            # Group nearby rows into tables
            potential_table_blocks.sort(key=lambda x: x["y_position"])
            current_table = []
            
            for i, block in enumerate(potential_table_blocks):
                if not current_table:
                    current_table.append(block)
                else:
                    # If blocks are close together vertically, they're likely the same table
                    y_diff = block["y_position"] - current_table[-1]["y_position"]
                    if y_diff < 30:  # 30 points threshold
                        current_table.append(block)
                    else:
                        # Process current table
                        if len(current_table) >= 2:
                            tables.append(self._process_table_blocks(current_table))
                        current_table = [block]
            
            # Process final table
            if len(current_table) >= 2:
                tables.append(self._process_table_blocks(current_table))
        
        return tables
    
    def _looks_like_table_row(self, text: str) -> bool:
        """Simple heuristic to identify potential table rows"""
        words = text.split()
        if len(words) < 2:
            return False
        
        # Count numeric values
        numeric_count = sum(1 for word in words if self._contains_number(word))
        return numeric_count >= 1 and len(words) >= 2
    
    def _contains_number(self, text: str) -> bool:
        """Check if text contains numerical data"""
        import re
        return bool(re.search(r'\d', text))
    
    def _process_table_blocks(self, table_blocks: List[Dict]) -> Dict[str, Any]:
        """Process a group of table blocks into structured table data"""
        rows = []
        for block in table_blocks:
            # Split text into columns (simple whitespace-based splitting)
            columns = block["text"].split()
            rows.append(columns)
        
        # Assume first row is headers if it contains fewer numbers
        headers = rows[0] if rows else []
        data_rows = rows[1:] if len(rows) > 1 else []
        
        return {
            "headers": headers,
            "rows": data_rows,
            "bbox": [
                min(block["bbox"][0] for block in table_blocks),
                min(block["bbox"][1] for block in table_blocks),
                max(block["bbox"][2] for block in table_blocks),
                max(block["bbox"][3] for block in table_blocks)
            ]
        }

# Singleton instance
pdf_service = PDFService()