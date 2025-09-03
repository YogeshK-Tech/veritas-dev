import openpyxl
import pandas as pd
from typing import Dict, Any, List
import structlog
from io import BytesIO
import json

logger = structlog.get_logger()

class ExcelService:
    def __init__(self):
        pass
    
    async def extract_data(self, file_content: bytes) -> Dict[str, Any]:
        """Extract structured data from Excel file"""
        try:
            workbook = openpyxl.load_workbook(BytesIO(file_content), data_only=True)
            workbook_with_formulas = openpyxl.load_workbook(BytesIO(file_content), data_only=False)
            
            sheets_data = {}
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                sheet_with_formulas = workbook_with_formulas[sheet_name]
                
                sheet_data = await self._extract_sheet_data(sheet, sheet_with_formulas)
                sheets_data[sheet_name] = sheet_data
            
            return {
                "sheets": sheets_data,
                "metadata": {
                    "sheet_names": list(workbook.sheetnames),
                    "total_sheets": len(workbook.sheetnames)
                }
            }
            
        except Exception as e:
            logger.error("Excel extraction failed", error=str(e))
            raise
    
    async def _extract_sheet_data(self, sheet, sheet_with_formulas) -> Dict[str, Any]:
        """Extract data from a single sheet"""
        # Get sheet dimensions
        max_row = sheet.max_row
        max_col = sheet.max_column
        
        # Extract all cell data
        cells_data = {}
        for row in range(1, min(max_row + 1, 1000)):  # Limit to 1000 rows for performance
            for col in range(1, min(max_col + 1, 50)):  # Limit to 50 columns
                cell = sheet.cell(row, col)
                cell_with_formula = sheet_with_formulas.cell(row, col)
                
                if cell.value is not None:
                    cell_ref = f"{openpyxl.utils.get_column_letter(col)}{row}"
                    cells_data[cell_ref] = {
                        "value": cell.value,
                        "data_type": type(cell.value).__name__,
                        "formula": cell_with_formula.value if str(cell_with_formula.value).startswith('=') else None,
                        "number_format": cell.number_format,
                        "font": {
                            "bold": cell.font.bold,
                            "size": cell.font.size
                        } if cell.font else None
                    }
        
        # Detect data regions
        data_regions = await self._detect_data_regions(cells_data, max_row, max_col)
        
        # Extract key metrics (cells that might be important KPIs)
        key_metrics = await self._identify_key_metrics(cells_data)
        
        return {
            "cells": cells_data,
            "data_regions": data_regions,
            "key_metrics": key_metrics,
            "dimensions": {
                "max_row": max_row,
                "max_col": max_col
            }
        }
    
    async def _detect_data_regions(self, cells_data: Dict, max_row: int, max_col: int) -> List[Dict[str, Any]]:
        """Detect contiguous data regions that might be tables"""
        regions = []
        
        # Simple algorithm: find rectangular regions with high cell density
        for start_row in range(1, min(max_row, 100), 5):  # Sample every 5 rows
            for start_col in range(1, min(max_col, 20), 3):  # Sample every 3 columns
                # Check for a potential table starting at this position
                region = self._analyze_region(cells_data, start_row, start_col, max_row, max_col)
                if region and region["cell_count"] >= 6:  # Minimum table size
                    regions.append(region)
        
        return regions
    
    def _analyze_region(self, cells_data: Dict, start_row: int, start_col: int, max_row: int, max_col: int) -> Dict[str, Any]:
        """Analyze a potential data region"""
        region_cells = []
        
        # Check up to 10x10 region
        for row in range(start_row, min(start_row + 10, max_row + 1)):
            for col in range(start_col, min(start_col + 10, max_col + 1)):
                cell_ref = f"{openpyxl.utils.get_column_letter(col)}{row}"
                if cell_ref in cells_data:
                    region_cells.append({
                        "cell_ref": cell_ref,
                        "value": cells_data[cell_ref]["value"],
                        "row": row,
                        "col": col
                    })
        
        if len(region_cells) >= 6:
            return {
                "start_cell": f"{openpyxl.utils.get_column_letter(start_col)}{start_row}",
                "cell_count": len(region_cells),
                "cells": region_cells,
                "density": len(region_cells) / 100  # Out of 10x10 grid
            }
        
        return None
    
    async def _identify_key_metrics(self, cells_data: Dict) -> List[Dict[str, Any]]:
        """Identify cells that might contain key financial metrics"""
        key_metrics = []
        
        for cell_ref, cell_info in cells_data.items():
            value = cell_info["value"]
            
            # Look for numeric values that might be KPIs
            if isinstance(value, (int, float)) and abs(value) > 0:
                # Check if cell has special formatting (bold, large font, etc.)
                is_emphasized = (
                    cell_info.get("font", {}).get("bold") or
                    (cell_info.get("font", {}).get("size", 0) > 12)
                )
                
                # Check if it's a large round number (often indicates summary metrics)
                is_round_number = (
                    isinstance(value, (int, float)) and
                    (value >= 1000 or (value > 0 and value < 1 and value != 0))
                )
                
                if is_emphasized or is_round_number:
                    key_metrics.append({
                        "cell_ref": cell_ref,
                        "value": value,
                        "data_type": cell_info["data_type"],
                        "formula": cell_info.get("formula"),
                        "formatting": cell_info.get("number_format"),
                        "emphasis_score": (
                            (2 if is_emphasized else 0) +
                            (1 if is_round_number else 0)
                        )
                    })
        
        # Sort by emphasis score
        key_metrics.sort(key=lambda x: x["emphasis_score"], reverse=True)
        return key_metrics[:50]  # Return top 50 potential key metrics

# Singleton instance
excel_service = ExcelService()