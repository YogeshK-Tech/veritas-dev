from typing import Dict, Any, List
import structlog
from app.services.ai_service import ai_service
from app.models.document import ValidationStatus
import asyncio
import re

logger = structlog.get_logger()

class AuditService:
    def __init__(self):
        self.ai_service = ai_service
    
    async def run_comprehensive_audit(self, pdf_data: Dict[str, Any], excel_data: Dict[str, Any], user_mappings: Dict[str, Any]) -> Dict[str, Any]:
        """Run a comprehensive audit comparing PDF and Excel data"""
        logger.info("Starting comprehensive audit")
        
        audit_results = {
            "summary": {
                "total_values_checked": 0,
                "matched": 0,
                "mismatched": 0,
                "formatting_errors": 0,
                "unverifiable": 0,
                "overall_accuracy": 0.0
            },
            "detailed_results": [],
            "recommendations": [],
            "risk_assessment": "low"
        }
        
        # Process each mapping
        validation_tasks = []
        for mapping in user_mappings.get("confirmed_mappings", []):
            task = self._validate_single_mapping(mapping, pdf_data, excel_data)
            validation_tasks.append(task)
        
        # Run validations concurrently (but limit concurrency to avoid rate limits)
        batch_size = 5
        all_results = []
        
        for i in range(0, len(validation_tasks), batch_size):
            batch = validation_tasks[i:i+batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            all_results.extend(batch_results)
        
        # Process results
        for result in all_results:
            if isinstance(result, Exception):
                logger.error("Validation task failed", error=str(result))
                continue
            
            if result:
                audit_results["detailed_results"].append(result)
                audit_results["summary"]["total_values_checked"] += 1
                
                status = result["validation_status"]
                if status == ValidationStatus.MATCHED:
                    audit_results["summary"]["matched"] += 1
                elif status == ValidationStatus.MISMATCHED:
                    audit_results["summary"]["mismatched"] += 1
                elif status == ValidationStatus.FORMATTING_ERROR:
                    audit_results["summary"]["formatting_errors"] += 1
                else:
                    audit_results["summary"]["unverifiable"] += 1
        
        # Calculate overall accuracy
        total = audit_results["summary"]["total_values_checked"]
        if total > 0:
            matched = audit_results["summary"]["matched"]
            audit_results["summary"]["overall_accuracy"] = (matched / total) * 100
        
        # Generate recommendations
        audit_results["recommendations"] = await self._generate_recommendations(audit_results)
        
        # Assess risk level
        audit_results["risk_assessment"] = self._assess_risk_level(audit_results)
        
        logger.info("Audit completed", 
                   total_checked=total, 
                   accuracy=audit_results["summary"]["overall_accuracy"])
        
        return audit_results
    
    async def _validate_single_mapping(self, mapping: Dict[str, Any], pdf_data: Dict[str, Any], excel_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single PDF-to-Excel mapping"""
        try:
            # Extract values from mapping
            pdf_value = mapping.get("pdf_value")
            pdf_context = mapping.get("pdf_context", "")
            excel_sheet = mapping.get("excel_sheet")
            excel_cell = mapping.get("excel_cell")
            
            # Get Excel value
            excel_value = self._get_excel_cell_value(excel_data, excel_sheet, excel_cell)
            excel_context = f"Sheet: {excel_sheet}, Cell: {excel_cell}"
            
            # Use AI to validate the mapping
            validation_result = await self.ai_service.validate_value(
                pdf_value=str(pdf_value),
                pdf_context=pdf_context,
                excel_value=str(excel_value),
                excel_context=excel_context
            )
            
            return {
                "mapping_id": mapping.get("id"),
                "pdf_value": pdf_value,
                "pdf_context": pdf_context,
                "pdf_slide": mapping.get("pdf_slide"),
                "excel_sheet": excel_sheet,
                "excel_cell": excel_cell,
                "excel_value": excel_value,
                "validation_status": validation_result["status"],
                "confidence_score": validation_result["confidence"],
                "ai_reasoning": validation_result["reasoning"],
                "normalized_pdf_value": validation_result.get("normalized_pdf_value"),
                "normalized_excel_value": validation_result.get("normalized_excel_value"),
                "discrepancy_type": validation_result.get("discrepancy_type"),
                "suggested_action": validation_result.get("suggested_action")
            }
            
        except Exception as e:
            logger.error("Single mapping validation failed", mapping=mapping, error=str(e))
            return {
                "mapping_id": mapping.get("id"),
                "validation_status": ValidationStatus.UNVERIFIABLE,
                "error": str(e)
            }
    
    def _get_excel_cell_value(self, excel_data: Dict[str, Any], sheet_name: str, cell_ref: str) -> Any:
        """Get value from Excel data structure"""
        try:
            sheet_data = excel_data["sheets"].get(sheet_name, {})
            cells = sheet_data.get("cells", {})
            cell_data = cells.get(cell_ref, {})
            return cell_data.get("value")
        except Exception as e:
            logger.warning("Failed to get Excel cell value", sheet=sheet_name, cell=cell_ref, error=str(e))
            return None
    
    async def _generate_recommendations(self, audit_results: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on audit results"""
        recommendations = []
        
        mismatched_count = audit_results["summary"]["mismatched"]
        formatting_errors = audit_results["summary"]["formatting_errors"]
        total_checked = audit_results["summary"]["total_values_checked"]
        accuracy = audit_results["summary"]["overall_accuracy"]
        
        if accuracy < 90:
            recommendations.append("Overall accuracy is below 90%. Consider reviewing data sources and calculation methods.")
        
        if mismatched_count > 0:
            recommendations.append(f"Found {mismatched_count} mismatched values. Review highlighted discrepancies in the detailed results.")
        
        if formatting_errors > 0:
            recommendations.append(f"Found {formatting_errors} formatting inconsistencies. Standardize number formatting across documents.")
        
        if total_checked < 10:
            recommendations.append("Limited data points checked. Consider adding more mappings for comprehensive validation.")
        
        # Analyze discrepancy patterns
        discrepancy_types = {}
        for result in audit_results["detailed_results"]:
            disc_type = result.get("discrepancy_type")
            if disc_type and disc_type != "null":
                discrepancy_types[disc_type] = discrepancy_types.get(disc_type, 0) + 1
        
        if discrepancy_types:
            most_common = max(discrepancy_types, key=discrepancy_types.get)
            recommendations.append(f"Most common discrepancy type: {most_common}. Focus on addressing this pattern.")
        
        return recommendations
    
    def _assess_risk_level(self, audit_results: Dict[str, Any]) -> str:
        """Assess overall risk level based on audit results"""
        accuracy = audit_results["summary"]["overall_accuracy"]
        mismatched_count = audit_results["summary"]["mismatched"]
        
        if accuracy >= 95 and mismatched_count == 0:
            return "low"
        elif accuracy >= 85 and mismatched_count <= 2:
            return "medium"
        else:
            return "high"

# Singleton instance
audit_service = AuditService()