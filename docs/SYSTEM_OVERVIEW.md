# Veritas AI Auditor - System Overview

## Architecture Overview

Veritas is built as a modern microservices architecture with the following key components:

### Backend Services (FastAPI)
- **Upload Service**: Handles file uploads and initial processing
- **AI Service**: Interfaces with Google Gemini 2.5 Pro for data extraction and analysis
- **Audit Service**: Performs comprehensive validation between PDF and Excel data
- **Report Service**: Generates multi-format audit reports
- **Metrics Service**: Tracks usage, costs, and performance

### Frontend Application (React.js)
- **Upload Interface**: Drag-and-drop file upload with validation
- **Mapping Confirmation**: Interactive UI for validating AI-suggested mappings
- **Audit Dashboard**: Real-time results with charts and detailed analysis
- **Report Viewer**: Multi-format report generation and viewing

### Data Flow

1. **File Upload**: Users upload PDF presentations and Excel spreadsheets
2. **AI Processing**: Gemini 2.5 Pro extracts structured data from both file types
3. **Mapping Suggestion**: AI suggests likely mappings between PDF and Excel values
4. **User Validation**: Interactive interface allows users to confirm/edit mappings
5. **Audit Execution**: Comprehensive validation runs on confirmed mappings
6. **Report Generation**: Multiple report formats available for different stakeholders

## Key Technologies

### AI Processing
- **Google Gemini 2.5 Pro**: Primary AI engine for document understanding
- **Custom Prompting**: Specialized prompts for financial document analysis
- **Context-Aware Validation**: Considers semantic meaning, not just exact matches

### Security
- **JWT Authentication**: Stateless authentication with configurable expiration
- **File Validation**: Comprehensive input validation and sanitization
- **Database Security**: SQL injection prevention, parameterized queries
- **CORS Protection**: Configurable cross-origin request handling

### Monitoring
- **Prometheus Metrics**: Industry-standard metrics collection
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Performance Tracking**: Request latency, throughput, error rates
- **Cost Monitoring**: AI token usage and estimated costs per operation

## Scalability Features

- **Async Processing**: Non-blocking I/O for high concurrency
- **Background Tasks**: CPU-intensive operations run asynchronously
- **Database Indexing**: Optimized queries for large datasets
- **Caching Strategy**: Redis integration for frequently accessed data
- **Horizontal Scaling**: Stateless design supports load balancing

## Data Models

### Document Management
- **Document**: File metadata and processing status
- **AuditSession**: Groups related documents for validation
- **ValidationResult**: Individual mapping validation outcomes

### Metrics & Analytics
- **UsageMetrics**: Operational metrics (latency, success rates)
- **AIUsage**: AI-specific metrics (tokens, costs, model performance)
- **AuditHistory**: Historical audit results for trending analysis