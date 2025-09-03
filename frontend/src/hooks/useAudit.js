import { useState } from 'react';
import { apiService } from '../services/api';

export const useAudit = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const createAuditSession = async (request) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiService.createAuditSession(request);
      return response;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const runAudit = async (auditSessionId) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiService.runAudit(auditSessionId);
      return response;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const getAuditResults = async (auditSessionId) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiService.getAuditResults(auditSessionId);
      return response;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return {
    loading,
    error,
    createAuditSession,
    runAudit,
    getAuditResults
  };
};