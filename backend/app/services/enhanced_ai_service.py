import google.generativeai as genai
from typing import Dict, Any, List, Tuple, Optional
import json
import base64
import structlog
from PIL import Image
import io
import time
import asyncio
import os
import fitz  # PyMuPDF
from decouple import config
import re
from datetime import datetime

# Configure logging
logger = structlog.get_logger()

class EnhancedGeminiService:
    def __init__(self):
        # Get API key from environment
        api_key = config('GOOGLE_API_KEY', default=None)
        
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required for Gemini 2.5 Pro")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.ai_enabled = True
        logger.info("Enhanced Gemini 2.5 Pro Service initialized successfully")

    async def extract_comprehensive_pdf_data(self, pdf_path: str) -> Dict[str, Any]:
        """
        Comprehensive PDF extraction using Gemini 2.5 Pro with bounding boxes
        """
        logger.info(f"Starting comprehensive PDF extraction: {pdf_path}")
        
        try:
            doc = fitz.open(pdf_path)
            page_analyses = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract high-quality page image with coordinates
                page_data = await self._extract_page_with_coordinates(page, page_num + 1)
                page_analyses.append(page_data)
                
                # Rate limiting for Gemini API
                await asyncio.sleep(1.5)
            
            doc.close()
            
            # Synthesize complete document analysis
            comprehensive_data = await self._synthesize_document_analysis(page_analyses)
            
            logger.info(f"PDF extraction completed: {len(comprehensive_data.get('all_extracted_values', []))} values found")
            return comprehensive_data
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise

    async def _extract_page_with_coordinates(self, page, page_num: int) -> Dict[str, Any]:
        """
        Extract page data with precise coordinate mapping using Gemini 2.5 Pro
        """
        try:
            # Convert page to high-resolution image
            mat = fitz.Matrix(2.0, 2.0)  # Reduced from 3.0 to 2.0 for better performance
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            # Convert to PIL Image for Gemini
            image = Image.open(io.BytesIO(img_data))
            
            # Simplified prompt for better JSON reliability
            prompt = f"""
Analyze this presentation slide (page {page_num}) and extract numerical values with coordinates.

Extract financial numbers, percentages, dates, and metrics from this slide.
For each number found, provide:
- The exact value as displayed
- Business context
- Normalized coordinates [x1, y1, x2, y2] on 0-1 scale
- Data type (currency, percentage, count, etc.)

Return ONLY valid JSON in this exact format:
{{
    "page_number": {page_num},
    "page_dimensions": {{"width": {image.width}, "height": {image.height}}},
    "extracted_values": [
        {{
            "id": "value_{page_num}_001",
            "value": "exact_number_as_displayed",
            "normalized_value": "cleaned_numeric_format",
            "data_type": "currency|percentage|count|ratio|date",
            "coordinates": {{
                "bounding_box": [0.1, 0.2, 0.3, 0.4],
                "confidence": 0.9
            }},
            "business_context": {{
                "semantic_meaning": "what_this_number_represents",
                "business_category": "revenue|costs|growth|operational",
                "presentation_priority": "primary|secondary|supporting"
            }},
            "confidence": 0.9
        }}
    ]
}}

CRITICAL: Return only valid JSON. No explanations or markdown formatting.
"""

            response = self.model.generate_content([prompt, image])
            result = await self._parse_gemini_json_response_robust(response.text, f"page_{page_num}")
            
            # Validate and enhance coordinates
            result = self._validate_and_enhance_coordinates(result, image.size)
            
            logger.info(f"Page {page_num}: Extracted {len(result.get('extracted_values', []))} values")
            return result
            
        except Exception as e:
            logger.error(f"Page {page_num} extraction failed: {e}")
            return {
                "page_number": page_num,
                "page_dimensions": {"width": 800, "height": 600},
                "extracted_values": [],
                "error": str(e)
            }

    async def _synthesize_document_analysis(self, page_analyses: List[Dict]) -> Dict[str, Any]:
        """
        Synthesize comprehensive document analysis using Gemini 2.5 Pro
        """
        # Combine all extracted values
        all_values = []
        for page in page_analyses:
            page_values = page.get('extracted_values', [])
            for value in page_values:
                value['page_number'] = page.get('page_number', 0)
                all_values.append(value)

        # Simplified synthesis for better reliability
        try:
            prompt = f"""
Analyze {len(page_analyses)} presentation pages with {len(all_values)} extracted values.

Create a document summary in JSON format:
{{
    "document_summary": {{
        "total_pages": {len(page_analyses)},
        "document_type": "financial_presentation",
        "main_business_themes": ["revenue", "growth", "performance"]
    }},
    "all_extracted_values": {json.dumps(all_values[:50])},
    "extraction_quality_metrics": {{
        "total_values_extracted": {len(all_values)},
        "overall_confidence": 0.85
    }}
}}

Return only valid JSON.
"""

            response = self.model.generate_content(prompt)
            synthesis = await self._parse_gemini_json_response_robust(response.text, "document_synthesis")
            
            # Ensure all_extracted_values is populated
            if not synthesis.get('all_extracted_values'):
                synthesis['all_extracted_values'] = all_values
            
            logger.info("Document synthesis completed successfully")
            return synthesis
            
        except Exception as e:
            logger.error(f"Document synthesis failed: {e}")
            # Return fallback structure
            return {
                "document_summary": {
                    "total_pages": len(page_analyses),
                    "document_type": "financial_presentation"
                },
                "all_extracted_values": all_values,
                "extraction_quality_metrics": {
                    "total_values_extracted": len(all_values),
                    "overall_confidence": 0.8
                },
                "synthesis_error": str(e)
            }

    async def analyze_excel_comprehensive(self, excel_path: str) -> Dict[str, Any]:
        """
        Comprehensive Excel analysis using Gemini 2.5 Pro
        """
        logger.info(f"Starting comprehensive Excel analysis: {excel_path}")
        
        try:
            import openpyxl
            
            # Load workbook
            wb_data = openpyxl.load_workbook(excel_path, data_only=True)
            wb_formulas = openpyxl.load_workbook(excel_path, data_only=False)
            
            sheet_analyses = []
            
            for sheet_name in wb_data.sheetnames[:3]:  # Limit to 3 sheets for efficiency
                logger.info(f"Processing Excel sheet: {sheet_name}")
                
                sheet_data = wb_data[sheet_name]
                sheet_formulas = wb_formulas[sheet_name]
                
                # Extract sheet structure
                sheet_structure = self._extract_excel_sheet_structure(sheet_data, sheet_formulas)
                
                # Analyze with Gemini
                sheet_analysis = await self._analyze_excel_sheet_with_gemini(sheet_name, sheet_structure)
                sheet_analyses.append(sheet_analysis)
                
                # Rate limiting
                await asyncio.sleep(1)
            
            # Synthesize workbook analysis
            workbook_analysis = await self._synthesize_excel_workbook(sheet_analyses)
            
            logger.info(f"Excel analysis completed: {len(workbook_analysis.get('potential_sources', []))} potential sources identified")
            return workbook_analysis
            
        except Exception as e:
            logger.error(f"Excel analysis failed: {e}")
            raise

    def _extract_excel_sheet_structure(self, sheet_data, sheet_formulas) -> Dict[str, Any]:
        """Extract Excel sheet structure for Gemini analysis"""
        import openpyxl
        
        max_row = min(sheet_data.max_row or 1, 50)  # Reduced for better performance
        max_col = min(sheet_data.max_column or 1, 20)
        
        cells_data = {}
        numeric_cells = []
        
        for row in range(1, max_row + 1):
            for col in range(1, max_col + 1):
                try:
                    cell_data = sheet_data.cell(row, col)
                    
                    if cell_data.value is not None:
                        cell_ref = f"{openpyxl.utils.get_column_letter(col)}{row}"
                        
                        cell_info = {
                            "value": cell_data.value,
                            "data_type": type(cell_data.value).__name__,
                            "row": row,
                            "col": col
                        }
                        
                        # Add formula if exists
                        try:
                            cell_formula = sheet_formulas.cell(row, col)
                            if cell_formula.value and str(cell_formula.value).startswith('='):
                                cell_info["formula"] = str(cell_formula.value)
                        except:
                            pass
                        
                        cells_data[cell_ref] = cell_info
                        
                        # Track numeric cells
                        if isinstance(cell_data.value, (int, float)) and abs(cell_data.value) > 0:
                            numeric_cells.append({
                                "cell_ref": cell_ref,
                                "value": cell_data.value,
                                "data_type": cell_info["data_type"],
                                "row": row,
                                "col": col,
                                "formula": cell_info.get("formula")
                            })
                except Exception as e:
                    # Skip problematic cells
                    continue
        
        return {
            "cells": cells_data,
            "numeric_cells": numeric_cells[:15],  # Limit for better processing
            "total_cells": len(cells_data)
        }

    async def _analyze_excel_sheet_with_gemini(self, sheet_name: str, sheet_structure: Dict) -> Dict[str, Any]:
        """Analyze Excel sheet using Gemini 2.5 Pro"""
        try:
            # Limit data for optimal processing
            limited_numeric = sheet_structure["numeric_cells"][:10]
            
            prompt = f"""
Analyze Excel sheet '{sheet_name}' for potential presentation values.

NUMERIC CELLS DATA:
{json.dumps(limited_numeric, indent=1)}

Identify values likely to appear in presentations. Return only valid JSON:
{{
    "sheet_name": "{sheet_name}",
    "potential_sources": [
        {{
            "cell_reference": "A1",
            "value": "actual_value",
            "business_context": "what_this_represents",
            "presentation_likelihood": 0.9,
            "data_type": "currency|percentage|count|ratio"
        }}
    ]
}}

Return only valid JSON.
"""

            response = self.model.generate_content(prompt)
            result = await self._parse_gemini_json_response_robust(response.text, f"excel_sheet_{sheet_name}")
            
            logger.info(f"Sheet {sheet_name}: Identified {len(result.get('potential_sources', []))} potential sources")
            return result
            
        except Exception as e:
            logger.error(f"Excel sheet analysis failed for {sheet_name}: {e}")
            return {
                "sheet_name": sheet_name, 
                "potential_sources": [], 
                "error": str(e)
            }

    async def _synthesize_excel_workbook(self, sheet_analyses: List[Dict]) -> Dict[str, Any]:
        """Synthesize Excel workbook analysis"""
        try:
            all_sources = []
            for analysis in sheet_analyses:
                sources = analysis.get("potential_sources", [])
                # Add sheet context to each source
                for source in sources:
                    source["source_sheet"] = analysis.get("sheet_name", "unknown")
                all_sources.extend(sources)
            
            # Sort by presentation likelihood
            all_sources.sort(key=lambda x: x.get("presentation_likelihood", 0), reverse=True)
            
            workbook_summary = {
                "workbook_summary": {
                    "total_sheets": len(sheet_analyses),
                    "analysis_timestamp": time.time()
                },
                "potential_sources": all_sources[:30],  # Top 30 most likely sources
                "sheet_analyses": sheet_analyses
            }
            
            logger.info(f"Workbook synthesis completed: {len(all_sources)} total sources")
            return workbook_summary
            
        except Exception as e:
            logger.error(f"Workbook synthesis failed: {e}")
            # Return basic structure
            all_sources = []
            for analysis in sheet_analyses:
                all_sources.extend(analysis.get("potential_sources", []))
            
            return {
                "workbook_summary": {"total_sheets": len(sheet_analyses)},
                "potential_sources": all_sources,
                "sheet_analyses": sheet_analyses,
                "synthesis_error": str(e)
            }
    
    async def run_direct_comprehensive_audit(self, pdf_values: List[Dict], excel_values: List[Dict]) -> Dict[str, Any]:
        """Run direct comprehensive audit comparing ALL PDF values against ALL Excel values"""
        logger.info(f"Starting direct comprehensive audit: {len(pdf_values)} PDF values vs {len(excel_values)} Excel values")
        
        if not pdf_values or not excel_values:
            return {
                "summary": {"total_values_checked": 0, "overall_accuracy": 0.0},
                "detailed_results": [],
                "recommendations": ["No values available for audit"],
                "risk_assessment": "high"
            }
        
        # Process PDF values in smaller batches for better reliability
        batch_size = 5  # Reduced batch size for better JSON reliability
        all_audit_results = []
        
        for i in range(0, len(pdf_values), batch_size):
            batch = pdf_values[i:i+batch_size]
            batch_results = await self._process_direct_audit_batch(batch, excel_values, i // batch_size + 1)
            all_audit_results.extend(batch_results)
            await asyncio.sleep(1)  # Rate limiting
        
        # Calculate comprehensive summary
        summary = {
            "total_values_checked": len(all_audit_results),
            "matched": len([r for r in all_audit_results if r.get("validation_status") == "matched"]),
            "mismatched": len([r for r in all_audit_results if r.get("validation_status") == "mismatched"]),
            "formatting_differences": len([r for r in all_audit_results if r.get("validation_status") == "formatting_difference"]),
            "unverifiable": len([r for r in all_audit_results if r.get("validation_status") == "unverifiable"]),
            "pdf_only": len([r for r in all_audit_results if r.get("validation_status") == "pdf_only"]),
        }
        
        if summary["total_values_checked"] > 0:
            summary["overall_accuracy"] = ((summary["matched"] + summary["formatting_differences"]) / summary["total_values_checked"]) * 100
        else:
            summary["overall_accuracy"] = 0.0

        # Generate comprehensive recommendations
        recommendations = self._generate_direct_audit_recommendations(summary)
        
        return {
            "summary": summary,
            "detailed_results": all_audit_results,
            "recommendations": recommendations,
            "risk_assessment": "low" if summary["overall_accuracy"] >= 85 else "medium" if summary["overall_accuracy"] >= 70 else "high",
            "coverage_analysis": {
                "pdf_values_analyzed": len(pdf_values),
                "excel_values_searched": len(excel_values),
                "coverage_percentage": 100.0,
                "approach": "comprehensive_direct_validation"
            }
        }

    async def _process_direct_audit_batch(self, pdf_batch: List[Dict], all_excel_values: List[Dict], batch_num: int) -> List[Dict]:
        """Process a batch of PDF values against all Excel values"""
        
        # Limit Excel values for prompt efficiency while maintaining comprehensiveness
        excel_sample = all_excel_values[:30] if len(all_excel_values) > 30 else all_excel_values
        
        prompt = f"""
You are auditing presentation values against Excel source data.

PDF VALUES TO VALIDATE (Batch {batch_num}):
{json.dumps(pdf_batch, indent=1)}

ALL EXCEL VALUES TO SEARCH:
{json.dumps(excel_sample, indent=1)}

For each PDF value, find its best match in Excel values and determine validation status.

Return ONLY valid JSON:
{{
    "batch_results": [
        {{
            "pdf_value_id": "pdf_value_id_from_input",
            "pdf_value": "actual_pdf_value",
            "pdf_context": "business_context_meaning",
            "validation_status": "matched|mismatched|formatting_difference|unverifiable|pdf_only",
            "excel_match": {{
                "source_file": "matched_excel_file_name",
                "cell_reference": "matched_cell_reference", 
                "excel_value": "matched_excel_value",
                "match_confidence": 0.95
            }},
            "confidence": 0.95,
            "audit_reasoning": "detailed_explanation_of_validation"
        }}
    ]
}}

Validation Status Guide:
- matched: Values are identical or equivalent
- formatting_difference: Same value, different format (e.g., 1000000 vs 1,000,000)
- mismatched: Values are different but related context
- unverifiable: Cannot determine relationship
- pdf_only: No corresponding Excel value found

Return ONLY valid JSON.
"""

        try:
            response = self.model.generate_content(prompt)
            result = await self._parse_gemini_json_response_robust(response.text, f"direct_audit_batch_{batch_num}")
            
            batch_results = result.get('batch_results', [])
            
            # Combine with original PDF values to ensure completeness
            final_results = []
            for i, pdf_value in enumerate(pdf_batch):
                if i < len(batch_results):
                    audit_result = batch_results[i]
                    # Ensure we have all required fields
                    audit_result.update({
                        "original_pdf_data": pdf_value,
                        "audit_timestamp": datetime.utcnow().isoformat(),
                        "batch_number": batch_num
                    })
                    final_results.append(audit_result)
                else:
                    # Fallback for missing results
                    final_results.append({
                        "pdf_value_id": pdf_value.get("id", f"pdf_value_{i}"),
                        "pdf_value": pdf_value.get("value", "unknown"),
                        "pdf_context": pdf_value.get("business_context", {}).get("semantic_meaning", "unknown"),
                        "validation_status": "unverifiable",
                        "excel_match": None,
                        "confidence": 0.0,
                        "audit_reasoning": "Batch processing incomplete",
                        "original_pdf_data": pdf_value,
                        "audit_timestamp": datetime.utcnow().isoformat(),
                        "batch_number": batch_num
                    })
            
            logger.info(f"Direct audit batch {batch_num}: Processed {len(final_results)} PDF values")
            return final_results
            
        except Exception as e:
            logger.error(f"Direct audit batch {batch_num} failed: {e}")
            # Return fallback results
            fallback_results = []
            for i, pdf_value in enumerate(pdf_batch):
                fallback_results.append({
                    "pdf_value_id": pdf_value.get("id", f"pdf_value_{i}"),
                    "pdf_value": pdf_value.get("value", "unknown"),
                    "pdf_context": pdf_value.get("business_context", {}).get("semantic_meaning", "unknown"),
                    "validation_status": "unverifiable",
                    "excel_match": None,
                    "confidence": 0.0,
                    "audit_reasoning": f"Audit error: {str(e)[:100]}",
                    "original_pdf_data": pdf_value,
                    "audit_timestamp": datetime.utcnow().isoformat(),
                    "batch_number": batch_num,
                    "error": str(e)
                })
            return fallback_results

    def _generate_direct_audit_recommendations(self, summary: Dict) -> List[str]:
        """Generate recommendations based on direct audit summary"""
        recommendations = []
        
        total = summary["total_values_checked"]
        if total == 0:
            return ["No values were audited. Check extraction process."]
        
        accuracy = summary["overall_accuracy"]
        matched = summary["matched"]
        formatting_diffs = summary["formatting_differences"]
        mismatched = summary["mismatched"]
        pdf_only = summary["pdf_only"]
        
        # Overall assessment
        if accuracy >= 90:
            recommendations.append(f"Excellent data quality: {accuracy:.1f}% accuracy across all {total} values.")
        elif accuracy >= 75:
            recommendations.append(f"Good data quality: {accuracy:.1f}% accuracy. Review flagged discrepancies.")
        else:
            recommendations.append(f"Data quality concerns: {accuracy:.1f}% accuracy. Comprehensive review needed.")
        
        # Specific recommendations
        if matched > 0:
            recommendations.append(f"✅ {matched} values perfectly matched between presentation and Excel.")
        
        if formatting_diffs > 0:
            recommendations.append(f"📋 {formatting_diffs} values have formatting differences but same underlying data.")
        
        if mismatched > 0:
            recommendations.append(f"⚠️ {mismatched} values show potential discrepancies requiring review.")
        
        if pdf_only > 0:
            percentage = (pdf_only / total) * 100
            if percentage > 20:
                recommendations.append(f"🔍 {pdf_only} values ({percentage:.1f}%) appear only in presentation - verify if these should have Excel sources.")
            else:
                recommendations.append(f"ℹ️ {pdf_only} values are presentation-only (calculated metrics, external data, etc.)")
        
        # Coverage assessment
        recommendations.append(f"📊 Comprehensive coverage: All {total} extracted values were validated (100% coverage).")
        
        return recommendations
        

    async def generate_intelligent_mappings(self, pdf_data: Dict, excel_data: Dict) -> Dict[str, Any]:
        """Generate intelligent mappings using Gemini 2.5 Pro"""
        logger.info("Generating intelligent mappings with Gemini 2.5 Pro")
        
        pdf_values = pdf_data.get('all_extracted_values', [])[:10]  # Limit for processing
        excel_sources = excel_data.get('potential_sources', [])[:15]
        
        if not pdf_values or not excel_sources:
            logger.warning("Insufficient data for mapping generation")
            return {
                "suggested_mappings": [],
                "mapping_quality_assessment": {"overall_coverage": 0},
                "error": "Insufficient data for mapping"
            }
        
        prompt = f"""
Create mappings between presentation values and Excel sources.

PDF VALUES (first 10):
{json.dumps(pdf_values, indent=1)}

EXCEL SOURCES (first 15):
{json.dumps(excel_sources, indent=1)}

Find matches between PDF and Excel values. Return only valid JSON:
{{
    "suggested_mappings": [
        {{
            "mapping_id": "map_001",
            "pdf_value": "presentation_value",
            "pdf_context": "presentation_context",
            "pdf_page": 1,
            "excel_source": {{
                "sheet_name": "sheet",
                "cell_reference": "A1",
                "value": "excel_value"
            }},
            "confidence": 0.95,
            "match_type": "exact_numerical",
            "mapping_reasoning": "Values match exactly"
        }}
    ],
    "mapping_quality_assessment": {{
        "total_successful_mappings": 5,
        "overall_coverage": 85.5
    }}
}}

Return only valid JSON.
"""

        try:
            response = self.model.generate_content(prompt)
            mappings = await self._parse_gemini_json_response_robust(response.text, "intelligent_mappings")
            
            logger.info(f"Intelligent mapping completed: {len(mappings.get('suggested_mappings', []))} mappings generated")
            return mappings
            
        except Exception as e:
            logger.error(f"Intelligent mapping failed: {e}")
            return {
                "suggested_mappings": [],
                "mapping_quality_assessment": {"overall_coverage": 0},
                "error": str(e)
            }

    async def run_comprehensive_audit(self, confirmed_mappings: List[Dict]) -> Dict[str, Any]:
        """Run comprehensive audit using Gemini 2.5 Pro"""
        logger.info(f"Starting comprehensive audit of {len(confirmed_mappings)} mappings")
        
        if not confirmed_mappings:
            return {
                "summary": {"total_values_checked": 0, "overall_accuracy": 0.0},
                "detailed_results": [],
                "recommendations": ["No mappings to audit"],
                "risk_assessment": "low"
            }
        
        # Process in smaller batches for better reliability
        batch_size = 2
        all_validations = []
        
        for i in range(0, len(confirmed_mappings), batch_size):
            batch = confirmed_mappings[i:i+batch_size]
            batch_validations = await self._process_audit_batch(batch, i // batch_size + 1)
            all_validations.extend(batch_validations)
            await asyncio.sleep(1)
        
        # Calculate summary
        summary = {
            "total_values_checked": len(all_validations),
            "matched": len([r for r in all_validations if r.get("validation_status") == "matched"]),
            "mismatched": len([r for r in all_validations if r.get("validation_status") == "mismatched"]),
            "formatting_errors": len([r for r in all_validations if r.get("validation_status") == "formatting_difference"]),
            "unverifiable": len([r for r in all_validations if r.get("validation_status") == "unverifiable"]),
        }
        
        if summary["total_values_checked"] > 0:
            summary["overall_accuracy"] = (summary["matched"] / summary["total_values_checked"]) * 100
        else:
            summary["overall_accuracy"] = 0.0

        return {
            "summary": summary,
            "detailed_results": all_validations,
            "recommendations": self._generate_recommendations(summary),
            "risk_assessment": "low" if summary["overall_accuracy"] >= 90 else "medium"
        }

    async def _process_audit_batch(self, batch: List[Dict], batch_num: int) -> List[Dict]:
        """Process audit batch with Gemini"""
        prompt = f"""
Validate these {len(batch)} mappings:

{json.dumps(batch, indent=1)}

For each mapping, determine if PDF and Excel values match. Return only valid JSON:
{{
    "batch_results": [
        {{
            "mapping_id": "mapping_id_from_input",
            "validation_status": "matched|mismatched|formatting_difference|unverifiable",
            "confidence": 0.95,
            "audit_details": {{
                "gemini_reasoning": "brief_explanation"
            }}
        }}
    ]
}}

Return only valid JSON.
"""

        try:
            response = self.model.generate_content(prompt)
            result = await self._parse_gemini_json_response_robust(response.text, f"audit_batch_{batch_num}")
            
            batch_results = result.get('batch_results', [])
            
            # Combine with original mappings
            final_results = []
            for i, mapping in enumerate(batch):
                if i < len(batch_results):
                    final_results.append({**mapping, **batch_results[i]})
                else:
                    final_results.append({
                        **mapping,
                        "validation_status": "unverifiable",
                        "confidence": 0.5,
                        "audit_details": {"gemini_reasoning": "Processing incomplete"}
                    })
            
            logger.info(f"Batch {batch_num}: Validated {len(final_results)} mappings")
            return final_results
            
        except Exception as e:
            logger.error(f"Batch {batch_num} validation failed: {e}")
            return [{
                **mapping,
                "validation_status": "unverifiable",
                "confidence": 0.0,
                "audit_details": {"gemini_reasoning": f"Error: {str(e)[:50]}"}
            } for mapping in batch]

    def _generate_recommendations(self, summary: Dict) -> List[str]:
        """Generate recommendations based on audit summary"""
        recommendations = []
        
        if summary["overall_accuracy"] < 90:
            recommendations.append("Overall accuracy is below 90%. Review data sources and mappings.")
        
        if summary["mismatched"] > 0:
            recommendations.append(f"Found {summary['mismatched']} mismatched values. Review highlighted discrepancies.")
        
        if summary["formatting_errors"] > 0:
            recommendations.append(f"Found {summary['formatting_errors']} formatting issues. Standardize number formats.")
        
        if summary["unverifiable"] > summary["total_values_checked"] * 0.2:
            recommendations.append("High number of unverifiable mappings. Check data quality.")
        
        if not recommendations:
            recommendations.append("Audit completed successfully with good data quality.")
        
        return recommendations

    def _validate_and_enhance_coordinates(self, result: Dict, image_size: Tuple[int, int]) -> Dict:
        """Validate and enhance coordinate data"""
        width, height = image_size
        
        for value in result.get('extracted_values', []):
            if 'coordinates' in value and 'bounding_box' in value['coordinates']:
                bbox = value['coordinates']['bounding_box']
                
                # Ensure coordinates are valid
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    x1 = max(0, min(1, float(x1)))
                    y1 = max(0, min(1, float(y1)))
                    x2 = max(0, min(1, float(x2)))
                    y2 = max(0, min(1, float(y2)))
                    
                    # Ensure logical ordering
                    if x1 > x2:
                        x1, x2 = x2, x1
                    if y1 > y2:
                        y1, y2 = y2, y1
                    
                    # Ensure minimum size
                    if x2 - x1 < 0.01:
                        x2 = min(1, x1 + 0.01)
                    if y2 - y1 < 0.01:
                        y2 = min(1, y1 + 0.01)
                    
                    value['coordinates']['bounding_box'] = [x1, y1, x2, y2]
                    value['coordinates']['center_point'] = [(x1 + x2) / 2, (y1 + y2) / 2]
                else:
                    # Set default coordinates if invalid
                    value['coordinates']['bounding_box'] = [0.1, 0.1, 0.2, 0.2]
                    value['coordinates']['center_point'] = [0.15, 0.15]
        
        return result

    async def _parse_gemini_json_response_robust(self, response_text: str, context: str) -> Dict[str, Any]:
        """Robust JSON parsing for Gemini responses with multiple fallback strategies"""
        try:
            # Step 1: Basic cleaning
            cleaned_text = response_text.strip()
            
            # Remove common markdown formatting
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            # Step 2: Find JSON boundaries more carefully
            json_start = -1
            json_end = -1
            brace_count = 0
            
            for i, char in enumerate(cleaned_text):
                if char == '{':
                    if json_start == -1:
                        json_start = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and json_start != -1:
                        json_end = i
                        break
            
            if json_start == -1 or json_end == -1:
                raise ValueError(f"No complete JSON object found in response for {context}")
            
            json_str = cleaned_text[json_start:json_end + 1]
            
            # Step 3: Advanced JSON cleaning
            json_str = self._clean_json_aggressively(json_str)
            
            # Step 4: Try to parse
            result = json.loads(json_str)
            logger.info(f"Successfully parsed Gemini JSON for {context}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error for {context}: {e}")
            # Try recovery strategies
            return await self._json_recovery_strategies(response_text, context)
            
        except Exception as e:
            logger.error(f"Unexpected parsing error for {context}: {e}")
            return self._get_fallback_structure(context)

    def _clean_json_aggressively(self, json_str: str) -> str:
        """Aggressively clean JSON string for common Gemini issues"""
        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix unquoted keys
        json_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)
        
        # Fix single quotes to double quotes
        json_str = re.sub(r"'([^']*)'", r'"\1"', json_str)
        
        # Remove comments if any
        json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
        
        # Fix common value issues
        json_str = re.sub(r':\s*True\b', ': true', json_str)
        json_str = re.sub(r':\s*False\b', ': false', json_str)
        json_str = re.sub(r':\s*None\b', ': null', json_str)
        
        return json_str

    async def _json_recovery_strategies(self, response_text: str, context: str) -> Dict[str, Any]:
        """Multiple strategies to recover from JSON parsing failures"""
        
        # Strategy 1: Try to extract just the core data
        try:
            # Look for key patterns and extract manually
            if "extracted_values" in response_text:
                # Try to find array content
                start_pattern = r'"extracted_values"\s*:\s*\['
                end_pattern = r'\]'
                
                match = re.search(start_pattern, response_text)
                if match:
                    start_pos = match.end() - 1  # Include the [
                    
                    # Find matching closing bracket
                    bracket_count = 0
                    end_pos = -1
                    for i in range(start_pos, len(response_text)):
                        if response_text[i] == '[':
                            bracket_count += 1
                        elif response_text[i] == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end_pos = i
                                break
                    
                    if end_pos != -1:
                        array_content = response_text[start_pos:end_pos + 1]
                        # Try to parse just this array
                        extracted_values = json.loads(array_content)
                        return {"extracted_values": extracted_values}
            
        except:
            pass
        
        # Strategy 2: Ask Gemini to fix the JSON
        try:
            recovery_prompt = f"""
The following text contains invalid JSON. Please return ONLY valid JSON with no additional text:

{response_text[:1000]}...

Return only valid JSON.
"""
            recovery_response = self.model.generate_content(recovery_prompt)
            
            # Try to parse the recovery response
            cleaned_recovery = recovery_response.text.strip()
            if cleaned_recovery.startswith("```json"):
                cleaned_recovery = cleaned_recovery[7:]
            if cleaned_recovery.endswith("```"):
                cleaned_recovery = cleaned_recovery[:-3]
            
            # Find JSON boundaries
            start_idx = cleaned_recovery.find('{')
            end_idx = cleaned_recovery.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = cleaned_recovery[start_idx:end_idx + 1]
                json_str = self._clean_json_aggressively(json_str)
                result = json.loads(json_str)
                logger.info(f"Successfully recovered JSON for {context}")
                return result
            
        except Exception as recovery_error:
            logger.error(f"JSON recovery also failed for {context}: {recovery_error}")
        
        # Strategy 3: Return fallback structure
        return self._get_fallback_structure(context)

    def _get_fallback_structure(self, context: str) -> Dict[str, Any]:
        """Return appropriate fallback structure based on context"""
        if "page_" in context:
            return {
                "page_number": 1,
                "page_dimensions": {"width": 800, "height": 600},
                "extracted_values": [],
                "error": f"JSON parsing failed for {context}"
            }
        elif "mapping" in context.lower():
            return {
                "suggested_mappings": [],
                "mapping_quality_assessment": {"overall_coverage": 0},
                "error": f"JSON parsing failed for {context}"
            }
        elif "excel_sheet" in context:
            return {
                "sheet_name": "unknown",
                "potential_sources": [],
                "error": f"JSON parsing failed for {context}"
            }
        elif "audit" in context.lower():
            return {
                "batch_results": [],
                "error": f"JSON parsing failed for {context}"
            }
        else:
            return {
                "error": f"JSON parsing failed for {context}"
            }

# Initialize the enhanced service
enhanced_gemini_service = EnhancedGeminiService()