import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8005/api';

class ApiService {
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 60000, // Increased timeout for AI operations
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('veritas_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response.data,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('veritas_token');
          window.location.href = '/';
        }
        const message = error.response?.data?.detail || error.message || 'An error occurred';
        throw new Error(message);
      }
    );
  }

  // Authentication - Updated to match backend
  async login(credentials) {
    const response = await this.client.post('/auth/login', credentials);
    return response;
  }

  async validateToken() {
    const response = await this.client.get('/auth/validate');
    return response;
  }

  // Document upload and processing - Fixed to match backend
  async uploadDocuments(formData) {
    const response = await this.client.post('/upload/documents', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response;
  }

  async processDocuments(sessionId) {
    const response = await this.client.post(`/process/${sessionId}`);
    return response;
  }

  async suggestMappings(sessionId) {
    const response = await this.client.post(`/ai/suggest-mappings/${sessionId}`);
    return response;
  }

  // Audit operations - Fixed to match backend
  async createAuditSession(request) {
    const response = await this.client.post('/audit/create', request);
    return response;
  }

  async runAudit(auditSessionId) {
    const response = await this.client.post(`/audit/run/${auditSessionId}`);
    return response;
  }

  async getAuditResults(auditSessionId) {
    const response = await this.client.get(`/audit/${auditSessionId}`);
    return response;
  }

  // Statistics
  async getStats() {
    const response = await this.client.get('/documents/stats');
    return response;
  }

  // Health check
  async healthCheck() {
    const response = await this.client.get('/health');
    return response;
  }
}

export const apiService = new ApiService();