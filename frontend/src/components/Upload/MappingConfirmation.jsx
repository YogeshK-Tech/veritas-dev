import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Check, X, AlertTriangle, ArrowRight, ArrowLeft } from 'lucide-react';

import { apiService } from '../../services/api';
import LoadingSpinner from '../Common/LoadingSpinner';

const MappingConfirmation = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  
  const [mappingSuggestions, setMappingSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
  console.log('Location state:', location.state); // Add this debug line
  
  if (location.state?.mappingSuggestions) {
    const suggestions = location.state.mappingSuggestions.suggested_mappings || [];
    console.log('Raw suggestions:', suggestions); // Add this debug line
    
    setMappingSuggestions(suggestions.map((suggestion, index) => ({
      ...suggestion,
      id: `mapping_${index}`,
      confirmed: suggestion.confidence >= 0.8,
      userModified: false
    })));
  } else {
    navigate('/upload');
  }
}, [location.state, navigate]);

  const handleConfirmMapping = (mappingId) => {
    setMappingSuggestions(prev => 
      prev.map(mapping => 
        mapping.id === mappingId 
          ? { ...mapping, confirmed: true }
          : mapping
      )
    );
  };

  const handleRejectMapping = (mappingId) => {
    setMappingSuggestions(prev => 
      prev.filter(mapping => mapping.id !== mappingId)
    );
    toast.info('Mapping removed');
  };

  const handleEditMapping = (mappingId, field, value) => {
    setMappingSuggestions(prev =>
      prev.map(mapping =>
        mapping.id === mappingId
          ? { ...mapping, [field]: value, userModified: true, confirmed: false }
          : mapping
      )
    );
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-100';
    if (confidence >= 0.6) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getConfidenceText = (confidence) => {
    if (confidence >= 0.8) return 'High';
    if (confidence >= 0.6) return 'Medium';
    return 'Low';
  };

  const startAudit = async () => {
    const confirmedMappingsList = mappingSuggestions.filter(m => m.confirmed);
    
    if (confirmedMappingsList.length === 0) {
      toast.error('Please confirm at least one mapping before starting audit');
      return;
    }

    setLoading(true);

    try {
      // Step 1: Create audit session
      const auditRequest = {
        upload_session_id: sessionId,
        confirmed_mappings: confirmedMappingsList.map(mapping => ({
          mapping_id: mapping.mapping_id,
          pdf_value: mapping.pdf_value,
          pdf_context: mapping.pdf_context,
          pdf_slide: mapping.pdf_slide,
          excel_sheet: mapping.excel_sheet,
          excel_cell: mapping.excel_cell,
          excel_value: mapping.excel_value,
          confidence: mapping.confidence
        }))
      };

      const createResponse = await apiService.createAuditSession(auditRequest);
      
      // Step 2: Run the audit
      const auditResponse = await apiService.runAudit(createResponse.audit_session_id);
      
      toast.success('Audit completed successfully!');
      navigate(`/audit/${createResponse.audit_session_id}`, {
        state: {
          auditResults: auditResponse.audit_results,
          sessionId: createResponse.audit_session_id
        }
      });

    } catch (error) {
      console.error('Audit failed:', error);
      toast.error('Audit failed: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <LoadingSpinner size="xl" text="Running AI audit..." />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Confirm Data Mappings
          </h2>
          <p className="text-gray-600 mb-6">
            Review AI-suggested mappings between your presentation and source data. 
            Confirm accurate mappings and edit or remove incorrect ones.
          </p>

          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-blue-50 p-4 rounded-lg">
              <p className="text-sm font-medium text-blue-600">Total Suggestions</p>
              <p className="text-2xl font-bold text-blue-900">{mappingSuggestions.length}</p>
            </div>
            <div className="bg-green-50 p-4 rounded-lg">
              <p className="text-sm font-medium text-green-600">Confirmed</p>
              <p className="text-2xl font-bold text-green-900">
                {mappingSuggestions.filter(m => m.confirmed).length}
              </p>
            </div>
            <div className="bg-yellow-50 p-4 rounded-lg">
              <p className="text-sm font-medium text-yellow-600">High Confidence</p>
              <p className="text-2xl font-bold text-yellow-900">
                {mappingSuggestions.filter(m => m.confidence >= 0.8).length}
              </p>
            </div>
            <div className="bg-red-50 p-4 rounded-lg">
              <p className="text-sm font-medium text-red-600">Needs Review</p>
              <p className="text-2xl font-bold text-red-900">
                {mappingSuggestions.filter(m => m.confidence < 0.6).length}
              </p>
            </div>
          </div>

          {/* Mappings List */}
          <div className="space-y-4 max-h-96 overflow-y-auto custom-scrollbar">
            {mappingSuggestions.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-gray-500">No mappings to review</p>
              </div>
            ) : (
              mappingSuggestions.map((mapping) => (
                <MappingCard
                  key={mapping.id}
                  mapping={mapping}
                  onConfirm={handleConfirmMapping}
                  onReject={handleRejectMapping}
                  onEdit={handleEditMapping}
                  getConfidenceColor={getConfidenceColor}
                  getConfidenceText={getConfidenceText}
                />
              ))
            )}
          </div>

          {/* Action Buttons */}
          <div className="mt-8 flex justify-between">
            <button
              onClick={() => navigate('/upload')}
              className="flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Upload
            </button>
            
            <button
              onClick={startAudit}
              disabled={mappingSuggestions.filter(m => m.confirmed).length === 0}
              className="px-6 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              Start Audit
              <ArrowRight className="ml-2 h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// MappingCard Component (same as before, with small improvements)
const MappingCard = ({ mapping, onConfirm, onReject, onEdit, getConfidenceColor, getConfidenceText }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValues, setEditValues] = useState({
    excel_sheet: mapping.excel_sheet,
    excel_cell: mapping.excel_cell
  });

  const handleSaveEdit = () => {
    onEdit(mapping.id, 'excel_sheet', editValues.excel_sheet);
    onEdit(mapping.id, 'excel_cell', editValues.excel_cell);
    setIsEditing(false);
    toast.success('Mapping updated');
  };

  return (
    <div className={`border rounded-lg p-4 ${mapping.confirmed ? 'border-green-300 bg-green-50' : 'border-gray-200'}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          {/* PDF Data */}
          <div className="mb-3">
            <h4 className="text-sm font-medium text-gray-900">Presentation Value</h4>
            <div className="mt-1 flex items-center space-x-2">
              <span className="text-lg font-semibold text-blue-600">{mapping.pdf_value}</span>
              <span className="text-xs text-gray-500">Slide {mapping.pdf_slide}</span>
            </div>
            <p className="text-sm text-gray-600">{mapping.pdf_context}</p>
          </div>

          {/* Arrow */}
          <div className="flex justify-center mb-3">
            <ArrowRight className="h-5 w-5 text-gray-400" />
          </div>

          {/* Excel Data */}
          <div className="mb-3">
            <h4 className="text-sm font-medium text-gray-900">Source Data</h4>
            {isEditing ? (
              <div className="mt-1 space-y-2">
                <input
                  type="text"
                  value={editValues.excel_sheet}
                  onChange={(e) => setEditValues({...editValues, excel_sheet: e.target.value})}
                  className="block w-full text-sm border-gray-300 rounded-md"
                  placeholder="Sheet name"
                />
                <input
                  type="text"
                  value={editValues.excel_cell}
                  onChange={(e) => setEditValues({...editValues, excel_cell: e.target.value})}
                  className="block w-full text-sm border-gray-300 rounded-md"
                  placeholder="Cell reference (e.g., A1)"
                />
                <div className="flex space-x-2">
                  <button
                    onClick={handleSaveEdit}
                    className="px-3 py-1 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setIsEditing(false)}
                    className="px-3 py-1 text-xs font-medium text-gray-700 bg-gray-200 rounded hover:bg-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-1 flex items-center space-x-2">
                <span className="text-lg font-semibold text-green-600">{mapping.excel_value}</span>
                <span className="text-xs text-gray-500">
                  {mapping.excel_sheet} • {mapping.excel_cell}
                </span>
                <button
                  onClick={() => setIsEditing(true)}
                  className="text-xs text-blue-600 hover:text-blue-800"
                >
                  Edit
                </button>
              </div>
            )}
          </div>

          {/* AI Reasoning */}
          <div className="text-xs text-gray-600 bg-gray-50 p-2 rounded">
            <strong>AI Analysis:</strong> {mapping.mapping_reasoning}
          </div>
        </div>

        {/* Actions & Confidence */}
        <div className="ml-4 flex flex-col items-end space-y-2">
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getConfidenceColor(mapping.confidence)}`}>
            {getConfidenceText(mapping.confidence)} ({Math.round(mapping.confidence * 100)}%)
          </span>

          {!mapping.confirmed ? (
            <div className="flex space-x-1">
              <button
                onClick={() => onConfirm(mapping.id)}
                className="p-1 text-green-600 hover:text-green-800 hover:bg-green-100 rounded"
                title="Confirm mapping"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                onClick={() => onReject(mapping.id)}
                className="p-1 text-red-600 hover:text-red-800 hover:bg-red-100 rounded"
                title="Reject mapping"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <span className="flex items-center text-green-600 text-xs">
              <Check className="h-4 w-4 mr-1" />
              Confirmed
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default MappingConfirmation;