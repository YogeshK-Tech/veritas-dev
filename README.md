# Veritas AI Auditor

Enterprise-grade AI presentation validation system that automatically validates Business PDF Presentations against source Excel spreadsheets.

## Features

- **AI-Powered Data Extraction**: Uses Google Gemini 2.5 Pro to extract and understand data from PDFs and Excel files
- **Intelligent Mapping**: Automatically suggests mappings between presentation values and source data
- **Interactive Validation**: User-friendly interface for confirming and editing data mappings
- **Comprehensive Auditing**: Context-aware validation with detailed discrepancy analysis
- **Multi-Format Reporting**: Interactive dashboards, annotated Excel files, and executive summaries
- **Enterprise Security**: JWT authentication, secure file storage, input validation
- **Usage Analytics**: Cost tracking, performance monitoring, error logging

## Technology Stack

**Backend:**
- FastAPI (Python)
- SQLAlchemy + SQLite/PostgreSQL
- Google Gemini 2.5 Pro for AI processing
- JWT authentication
- Prometheus metrics

**Frontend:**
- React.js 18
- Tailwind CSS
- Chart.js for visualizations
- Axios for API communication
- React Router for navigation

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 16+
- Google AI Studio API key

### Installation

1. Clone the repository
2. Run setup script: `scripts\setup.bat`
3. Configure environment variables
4. Start development servers: `scripts\run-dev.bat`

## Project Structure
## API Documentation

API documentation is available at `http://localhost:8000/docs` when running the development server.

## Security Features

- JWT-based authentication
- File upload validation and sanitization
- SQL injection prevention
- CORS configuration
- Rate limiting
- Secure file storage

## Monitoring & Metrics

- Prometheus metrics on port 8001
- Request latency tracking
- AI token usage monitoring
- Cost tracking per operation
- Error rate monitoring

## License

Enterprise License - Contact for commercial use