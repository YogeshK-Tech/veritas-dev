import structlog
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from app.models.document import UsageMetrics
from app.database.database import get_db
from typing import Optional
import time
import uuid

logger = structlog.get_logger()

# Prometheus metrics
REQUEST_COUNT = Counter('veritas_requests_total', 'Total requests', ['operation', 'status'])
REQUEST_LATENCY = Histogram('veritas_request_duration_seconds', 'Request latency', ['operation'])
AI_TOKEN_USAGE = Counter('veritas_ai_tokens_total', 'AI tokens used', ['model', 'operation'])
AI_COST = Counter('veritas_ai_cost_total', 'AI cost in USD', ['model', 'operation'])
ACTIVE_SESSIONS = Gauge('veritas_active_sessions', 'Number of active audit sessions')

def setup_metrics():
    """Setup Prometheus metrics server"""
    start_http_server(8001)
    logger.info("Metrics server started on port 8001")

async def track_operation(operation_type: str, latency_ms: float, success: bool, session_id: str, error_message: Optional[str] = None):
    """Track operation metrics"""
    status = "success" if success else "error"
    
    # Update Prometheus metrics
    REQUEST_COUNT.labels(operation=operation_type, status=status).inc()
    REQUEST_LATENCY.labels(operation=operation_type).observe(latency_ms / 1000)
    
    # Save to database
    try:
        db = next(get_db())
        usage_record = UsageMetrics(
            session_id=session_id,
            operation_type=operation_type,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message
        )
        db.add(usage_record)
        db.commit()
    except Exception as e:
        logger.error("Failed to save usage metrics", error=str(e))

async def track_ai_usage(operation_type: str, model: str, tokens_used: Optional[int] = None, 
                        latency_ms: float = 0, success: bool = True, error_message: Optional[str] = None):
    """Track AI-specific usage metrics"""
    
    # Update Prometheus metrics
    if tokens_used:
        AI_TOKEN_USAGE.labels(model=model, operation=operation_type).inc(tokens_used)
        
        # Estimate cost (rough estimates)
        cost_per_token = {
            "gemini-2.0-flash-exp": 0.000001,  # $1 per 1M tokens
            "gpt-4": 0.00003,  # $30 per 1M tokens
        }
        
        estimated_cost = tokens_used * cost_per_token.get(model, 0.000001)
        AI_COST.labels(model=model, operation=operation_type).inc(estimated_cost)
    
    # Save to database
    try:
        db = next(get_db())
        usage_record = UsageMetrics(
            session_id=str(uuid.uuid4()),
            operation_type=operation_type,
            ai_model_used=model,
            tokens_used=tokens_used,
            cost_usd=estimated_cost if tokens_used else None,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message
        )
        db.add(usage_record)
        db.commit()
    except Exception as e:
        logger.error("Failed to save AI usage metrics", error=str(e))