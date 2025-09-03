import google.generativeai as genai
import openai
from typing import List, Dict, Any, Optional
import json
import structlog
from app.config import settings
from app.utils.metrics import track_ai_usage
import time

logger = structlog.get_logger()

class AIService:
    def __init__(self):
        if settings.GOOGLE_API_KEY:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
    
    async def extract_pdf_content(self, pdf_text: str, pdf_images: List[bytes] = None) -> Dict[str, Any]:
        """Extract structured content from PDF using AI"""
        start_time = time.time()
        
        prompt = """
        You are an expert financial document analyzer. Extract all numerical data, tables, charts, and key financial metrics from this presentation.
        
        For each piece of data found, provide:
        1. The exact value as it appears
        2. The context (what the value represents)
        3. The slide/page number
        4. The location on the page (if determinable)
        5. The data type (currency, percentage, count, etc.)
        
        Return the results in this JSON format:
        {
            "extracted_values": [
                {
                    "value": "actual_value",
                    "context": "description_of_what_this_value_represents",
                    "slide_number": number,
                    "data_type": "currency|percentage|count|ratio",
                    "location": "approximate_location_on_slide",
                    "confidence": confidence_score_0_to_1
                }
            ],
            "tables": [
                {
                    "slide_number": number,
                    "table_data": "structured_table_as_text",
                    "headers": ["col1", "col2", ...],
                    "rows": [["val1", "val2", ...], ...]
                }
            ],
            "charts": [
                {
                    "slide_number": number,
                    "chart_type": "bar|line|pie|etc",
                    "data_points": ["extracted_data_points"],
                    "description": "chart_description"
                }
            ]
        }
        
        PDF Content:
        """ + pdf_text
        
        try:
            response = self.gemini_model.generate_content(prompt)
            result = self._parse_json_response(response.text)
            
            latency = (time.time() - start_time) * 1000
            await track_ai_usage(
                operation_type="pdf_extraction",
                model="gemini-2.0-flash-exp",
                tokens_used=len(prompt.split()) + len(response.text.split()),
                latency_ms=latency,
                success=True
            )
            
            return result
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            await track_ai_usage(
                operation_type="pdf_extraction",
                model="gemini-2.0-flash-exp",
                latency_ms=latency,
                success=False,
                error_message=str(e)
            )
            logger.error("PDF extraction failed", error=str(e))
            raise
    
    async def extract_excel_content(self, excel_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and understand Excel data using AI"""
        start_time = time.time()
        
        prompt = f"""
        You are an expert at analyzing Excel spreadsheets for financial data. Analyze this Excel file structure and identify all numerical data, formulas, and relationships.
        
        For each sheet, identify:
        1. Key financial metrics and their values
        2. Data tables and their structure
        3. Calculated fields and formulas
        4. Relationships between different data points
        
        Excel Structure:
        {json.dumps(excel_data, indent=2)}
        
        Return results in this JSON format:
        {{
            "sheets": [
                {{
                    "sheet_name": "name",
                    "key_metrics": [
                        {{
                            "metric_name": "name",
                            "value": "value",
                            "cell_reference": "A1",
                            "data_type": "currency|percentage|count|ratio",
                            "formula": "if_applicable"
                        }}
                    ],
                    "data_tables": [
                        {{
                            "table_name": "inferred_name",
                            "range": "A1:D10",
                            "headers": ["col1", "col2", ...],
                            "key_columns": ["important_columns"]
                        }}
                    ]
                }}
            ],
            "relationships": [
                {{
                    "source_sheet": "sheet1",
                    "source_cell": "A1",
                    "target_sheet": "sheet2",
                    "target_cell": "B2",
                    "relationship_type": "reference|calculation|summary"
                }}
            ]
        }}
        """
        
        try:
            response = self.gemini_model.generate_content(prompt)
            result = self._parse_json_response(response.text)
            
            latency = (time.time() - start_time) * 1000
            await track_ai_usage(
                operation_type="excel_extraction",
                model="gemini-2.0-flash-exp",
                tokens_used=len(prompt.split()) + len(response.text.split()),
                latency_ms=latency,
                success=True
            )
            
            return result
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            await track_ai_usage(
                operation_type="excel_extraction",
                model="gemini-2.0-flash-exp",
                latency_ms=latency,
                success=False,
                error_message=str(e)
            )
            logger.error("Excel extraction failed", error=str(e))
            raise
    
    async def suggest_mappings(self, pdf_data: Dict[str, Any], excel_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to suggest mappings between PDF values and Excel sources"""
        start_time = time.time()
        
        prompt = f"""
        You are an expert at mapping financial presentation data to source spreadsheets. Analyze the extracted PDF data and Excel data to suggest likely mappings.
        
        For each value in the PDF, suggest the most likely Excel source based on:
        1. Exact value matches
        2. Semantic similarity of context
        3. Data type compatibility
        4. Common financial reporting patterns
        
        PDF Data:
        {json.dumps(pdf_data, indent=2)}
        
        Excel Data:
        {json.dumps(excel_data, indent=2)}
        
        Return mappings in this JSON format:
        {{
            "suggested_mappings": [
                {{
                    "pdf_value": "value_from_pdf",
                    "pdf_context": "context_from_pdf",
                    "pdf_slide": slide_number,
                    "excel_sheet": "sheet_name",
                    "excel_cell": "A1",
                    "excel_value": "matching_value",
                    "confidence": confidence_score_0_to_1,
                    "mapping_reasoning": "why_this_mapping_makes_sense"
                }}
            ],
            "unmapped_pdf_values": [
                {{
                    "value": "value_without_clear_source",
                    "context": "context",
                    "slide": slide_number,
                    "suggestions": ["possible_reasons_no_match_found"]
                }}
            ],
            "unused_excel_data": [
                {{
                    "sheet": "sheet_name",
                    "cell": "A1",
                    "value": "unused_value",
                    "potential_use": "suggested_purpose"
                }}
            ]
        }}
        """
        
        try:
            response = self.gemini_model.generate_content(prompt)
            result = self._parse_json_response(response.text)
            
            latency = (time.time() - start_time) * 1000
            await track_ai_usage(
                operation_type="mapping_suggestion",
                model="gemini-2.0-flash-exp",
                tokens_used=len(prompt.split()) + len(response.text.split()),
                latency_ms=latency,
                success=True
            )
            
            return result
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            await track_ai_usage(
                operation_type="mapping_suggestion",
                model="gemini-2.0-flash-exp",
                latency_ms=latency,
                success=False,
                error_message=str(e)
            )
            logger.error("Mapping suggestion failed", error=str(e))
            raise
    
    async def validate_value(self, pdf_value: str, pdf_context: str, excel_value: str, excel_context: str) -> Dict[str, Any]:
        """Use AI to validate a single value mapping"""
        start_time = time.time()
        
        prompt = f"""
        You are a financial auditor validating data consistency. Compare these values and determine if they match, considering:
        
        1. Exact numerical match
        2. Formatting differences (e.g., "$1,000" vs "1000")
        3. Rounding differences
        4. Unit conversions (millions, thousands, etc.)
        5. Contextual appropriateness
        
        PDF Value: "{pdf_value}"
        PDF Context: "{pdf_context}"
        
        Excel Value: "{excel_value}"
        Excel Context: "{excel_context}"
        
        Return validation in this JSON format:
        {{
            "status": "matched|mismatched|formatting_error|unverifiable",
            "confidence": confidence_score_0_to_1,
            "reasoning": "detailed_explanation_of_validation_decision",
            "normalized_pdf_value": "standardized_pdf_value",
            "normalized_excel_value": "standardized_excel_value",
            "discrepancy_type": "exact_match|formatting_difference|rounding_difference|unit_conversion|value_mismatch|context_mismatch|null",
            "suggested_action": "recommendation_for_user"
        }}
        """
        
        try:
            response = self.gemini_model.generate_content(prompt)
            result = self._parse_json_response(response.text)
            
            latency = (time.time() - start_time) * 1000
            await track_ai_usage(
                operation_type="value_validation",
                model="gemini-2.0-flash-exp",
                tokens_used=len(prompt.split()) + len(response.text.split()),
                latency_ms=latency,
                success=True
            )
            
            return result
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            await track_ai_usage(
                operation_type="value_validation",
                model="gemini-2.0-flash-exp",
                latency_ms=latency,
                success=False,
                error_message=str(e)
            )
            logger.error("Value validation failed", error=str(e))
            raise
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON from AI response, handling markdown formatting"""
        try:
            # Remove markdown code blocks if present
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            return json.loads(cleaned_text.strip())
        except json.JSONDecodeError as e:
            logger.error("Failed to parse AI response as JSON", response=response_text, error=str(e))
            raise ValueError(f"Invalid JSON response from AI: {str(e)}")

# Singleton instance
ai_service = AIService()