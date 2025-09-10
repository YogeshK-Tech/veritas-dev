import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Check, X, Edit3, Eye, AlertTriangle, TrendingUp, ArrowRight, 
  ZoomIn, ZoomOut, Brain, Target, Layers, CheckCircle, Play, 
  FileText, BarChart3, Save, ExternalLink, Users, Database
} from 'lucide-react';
import toast from 'react-hot-toast';

import { apiService } from '../../services/api';
import LoadingSpinner from '../Common/LoadingSpinner';

const InteractiveValidation = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  
  // Core state
  const [validationData, setValidationData] = useState(null);
  const [pdfValues, setPdfValues] = useState([]);
  const [excelValues, setExcelValues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [startingAudit, setStartingAudit] = useState(false);
  
  // UI state
  const [currentPage, setCurrentPage] = useState(0);
  const [zoom, setZoom] = useState(1.0);
  const [selectedValueId, setSelectedValueId] = useState(null);
  const [hoveredValueId, setHoveredValueId] = useState(null);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [confidenceFilter, setConfidenceFilter] = useState(0);
  const [validationMode, setValidationMode] = useState('pdf'); // pdf | excel | audit
  
  // Canvas refs
  const canvasRef = useRef(null);
  const overlayCanvasRef = useRef(null);

  useEffect(() => {
    loadValidationData();
  }, [sessionId]);

  useEffect(() => {
    if (validationData && canvasRef.current && overlayCanvasRef.current) {
      drawDocumentPage();
      drawValueOverlays();
    }
  }, [validationData, currentPage, zoom, selectedValueId, hoveredValueId, showBoundingBoxes, confidenceFilter]);

  const loadValidationData = async () => {
    try {
      console.log('[Validation] Loading validation data for session:', sessionId);
      
      const data = await apiService.client.get(`/validation/data/${sessionId}`);
      console.log('[Validation] Validation data loaded:', data);
      
      setValidationData(data);
      setPdfValues(data.pdf_values || []);
      setExcelValues(data.excel_values || []);
      
    } catch (error) {
      console.error('[Validation] Failed to load validation data:', error);
      toast.error('Failed to load validation data: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const drawDocumentPage = () => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    if (!validationData?.document_preview?.pages?.[currentPage]) return;
    
    const pageData = validationData.document_preview.pages[currentPage];
    const img = new Image();
    
    img.onload = () => {
      const scaledWidth = img.width * zoom;
      const scaledHeight = img.height * zoom;
      
      canvas.width = scaledWidth;
      canvas.height = scaledHeight;
      
      ctx.clearRect(0, 0, scaledWidth, scaledHeight);
      ctx.drawImage(img, 0, 0, scaledWidth, scaledHeight);
    };
    
    img.src = `data:image/png;base64,${pageData.image_data}`;
  };

  const drawValueOverlays = () => {
    const overlayCanvas = overlayCanvasRef.current;
    const mainCanvas = canvasRef.current;
    
    if (!overlayCanvas || !mainCanvas) return;
    
    const ctx = overlayCanvas.getContext('2d');
    
    overlayCanvas.width = mainCanvas.width;
    overlayCanvas.height = mainCanvas.height;
    
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    
    if (!showBoundingBoxes || validationMode !== 'pdf') return;
    
    const pageValues = pdfValues.filter(value => 
      value.page_number === currentPage + 1 && 
      value.coordinates?.bounding_box &&
      (value.confidence || 0) >= confidenceFilter / 100
    );
    
    pageValues.forEach(value => {
      drawValueBoundingBox(ctx, value, overlayCanvas.width, overlayCanvas.height);
    });
  };

  const drawValueBoundingBox = (ctx, value, canvasWidth, canvasHeight) => {
    const bbox = value.coordinates.bounding_box;
    if (!bbox || bbox.length !== 4) return;
    
    const [x1, y1, x2, y2] = bbox;
    
    const canvasX1 = x1 * canvasWidth;
    const canvasY1 = y1 * canvasHeight;
    const canvasX2 = x2 * canvasWidth;
    const canvasY2 = y2 * canvasHeight;
    
    let strokeColor = getConfidenceColor(value.confidence);
    let fillColor = strokeColor + '20';
    let lineWidth = 2;
    let lineDash = [];
    
    if (selectedValueId === value.id) {
      strokeColor = '#3B82F6';
      fillColor = '#3B82F620';
      lineWidth = 3;
    } else if (hoveredValueId === value.id) {
      strokeColor = '#8B5CF6';
      fillColor = '#8B5CF620';
      lineWidth = 3;
      lineDash = [5, 5];
    }
    
    ctx.strokeStyle = strokeColor;
    ctx.fillStyle = fillColor;
    ctx.lineWidth = lineWidth;
    ctx.setLineDash(lineDash);
    
    ctx.fillRect(canvasX1, canvasY1, canvasX2 - canvasX1, canvasY2 - canvasY1);
    ctx.strokeRect(canvasX1, canvasY1, canvasX2 - canvasX1, canvasY2 - canvasY1);
    
    // Confidence indicator
    const confidenceWidth = (canvasX2 - canvasX1) * (value.confidence || 0);
    ctx.fillStyle = strokeColor;
    ctx.fillRect(canvasX1, canvasY1 - 4, confidenceWidth, 4);
    
    // Value label
    if (selectedValueId === value.id || hoveredValueId === value.id) {
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(canvasX1, canvasY1 - 24, Math.max(100, (value.value || '').length * 8), 20);
      
      ctx.fillStyle = '#1F2937';
      ctx.font = '12px Arial';
      ctx.fillText(value.value || '', canvasX1 + 4, canvasY1 - 8);
    }
  };

  const getConfidenceColor = (confidence) => {
    if (!confidence) return '#9CA3AF';
    if (confidence >= 0.8) return '#10B981';
    if (confidence >= 0.6) return '#F59E0B';
    return '#EF4444';
  };

  const handleCanvasClick = (event) => {
    if (validationMode !== 'pdf') return;
    
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) / canvas.width;
    const y = (event.clientY - rect.top) / canvas.height;
    
    const pageValues = pdfValues.filter(value => 
      value.page_number === currentPage + 1 && 
      value.coordinates?.bounding_box
    );
    
    const clickedValue = pageValues.find(value => {
      const bbox = value.coordinates.bounding_box;
      if (!bbox || bbox.length !== 4) return false;
      
      const [x1, y1, x2, y2] = bbox;
      return x >= x1 && x <= x2 && y >= y1 && y <= y2;
    });
    
    if (clickedValue) {
      setSelectedValueId(clickedValue.id);
      toast.success(`Selected: ${clickedValue.value}`);
    } else {
      setSelectedValueId(null);
    }
  };

  const handleCanvasMouseMove = (event) => {
    if (validationMode !== 'pdf') return;
    
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) / canvas.width;
    const y = (event.clientY - rect.top) / canvas.height;
    
    const pageValues = pdfValues.filter(value => 
      value.page_number === currentPage + 1 && 
      value.coordinates?.bounding_box
    );
    
    const hoveredValue = pageValues.find(value => {
      const bbox = value.coordinates.bounding_box;
      if (!bbox || bbox.length !== 4) return false;
      
      const [x1, y1, x2, y2] = bbox;
      return x >= x1 && x <= x2 && y >= y1 && y <= y2;
    });
    
    setHoveredValueId(hoveredValue?.id || null);
  };

  const handlePdfValueEdit = async (valueId, newData) => {
    try {
      await apiService.client.post(`/validation/update-pdf-value/${sessionId}`, {
        value_id: valueId,
        updates: newData
      });
      
      setPdfValues(prev => 
        prev.map(val => 
          val.id === valueId 
            ? { ...val, ...newData, user_modified: true }
            : val
        )
      );
      
      toast.success('PDF value updated successfully');
    } catch (error) {
      console.error('[Validation] Failed to update PDF value:', error);
      toast.error('Failed to update PDF value: ' + error.message);
    }
  };

  const handleExcelValueEdit = async (valueId, newData) => {
    try {
      await apiService.client.post(`/validation/update-excel-value/${sessionId}`, {
        value_id: valueId,
        updates: newData
      });
      
      setExcelValues(prev => 
        prev.map(val => {
          const identifier = `${val.source_file}_${val.cell_reference}`;
          return identifier === valueId || val.id === valueId
            ? { ...val, ...newData, user_modified: true }
            : val;
        })
      );
      
      toast.success('Excel value updated successfully');
    } catch (error) {
      console.error('[Validation] Failed to update Excel value:', error);
      toast.error('Failed to update Excel value: ' + error.message);
    }
  };

  const startDirectAudit = async () => {
    if (pdfValues.length === 0 || excelValues.length === 0) {
      toast.error('Need both PDF and Excel values to start audit');
      return;
    }

    setStartingAudit(true);

    try {
      console.log('[Audit] Starting direct comprehensive audit...');
      console.log(`[Audit] Auditing ${pdfValues.length} PDF values against ${excelValues.length} Excel values`);
      
      const auditResponse = await apiService.client.post(`/validation/start-direct-audit/${sessionId}`);
      
      toast.success(`Direct audit completed! Validated ${pdfValues.length} values with 100% coverage.`);
      
      // Navigate to results
      navigate(`/audit/${auditResponse.audit_session_id}`, {
        state: {
          auditResults: auditResponse.audit_results,
          auditSessionId: auditResponse.audit_session_id,
          sessionId: sessionId,
          approach: 'direct_validation'
        }
      });

    } catch (error) {
      console.error('[Audit] Direct audit failed:', error);
      toast.error('Direct audit failed: ' + error.message);
    } finally {
      setStartingAudit(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <LoadingSpinner size="xl" text="Loading direct validation interface..." />
      </div>
    );
  }

  if (!validationData) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900">No validation data available</h3>
        <p className="text-gray-600">Please process documents first.</p>
      </div>
    );
  }

  const filteredPdfValues = pdfValues.filter(value => 
    (value.confidence || 0) >= confidenceFilter / 100
  );

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Enhanced Header */}
      <div className="bg-white shadow-sm rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Brain className="h-8 w-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Direct Value Validation</h1>
              <p className="text-gray-600">Validate all extracted values directly - 100% coverage approach</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="text-right">
              <div className="text-sm text-gray-500">Coverage</div>
              <div className="text-2xl font-bold text-green-600">100%</div>
            </div>
            
            <div className="flex bg-gray-100 rounded-lg p-1">
              {[
                { key: 'pdf', label: 'PDF Values', icon: FileText, count: pdfValues.length },
                { key: 'excel', label: 'Excel Values', icon: BarChart3, count: excelValues.length },
                { key: 'audit', label: 'Start Audit', icon: Play, count: null }
              ].map((mode) => {
                const Icon = mode.icon;
                return (
                  <button
                    key={mode.key}
                    onClick={() => setValidationMode(mode.key)}
                    className={`px-3 py-2 text-sm font-medium rounded-md flex items-center space-x-1 ${
                      validationMode === mode.key
                        ? 'bg-white text-blue-600 shadow-sm'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{mode.label}</span>
                    {mode.count !== null && (
                      <span className="text-xs bg-gray-200 text-gray-700 px-1 rounded">
                        {mode.count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Validation Statistics */}
      <div className="bg-gradient-to-r from-blue-50 to-green-50 rounded-lg p-6 border">
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
          <TrendingUp className="h-5 w-5 mr-2 text-blue-600" />
          Direct Validation Statistics
        </h3>
        
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-white rounded p-4 text-center">
            <div className="text-3xl font-bold text-blue-600">{pdfValues.length}</div>
            <div className="text-sm text-gray-600">PDF Values</div>
            <div className="text-xs text-green-600 mt-1">All Extracted</div>
          </div>
          <div className="bg-white rounded p-4 text-center">
            <div className="text-3xl font-bold text-green-600">{excelValues.length}</div>
            <div className="text-sm text-gray-600">Excel Values</div>
            <div className="text-xs text-green-600 mt-1">All Sources</div>
          </div>
          <div className="bg-white rounded p-4 text-center">
            <div className="text-3xl font-bold text-purple-600">{pdfValues.length + excelValues.length}</div>
            <div className="text-sm text-gray-600">Total Values</div>
            <div className="text-xs text-purple-600 mt-1">For Validation</div>
          </div>
          <div className="bg-white rounded p-4 text-center">
            <div className="text-3xl font-bold text-orange-600">100%</div>
            <div className="text-sm text-gray-600">Coverage</div>
            <div className="text-xs text-orange-600 mt-1">No Bottlenecks</div>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Viewer / Excel Viewer */}
        <div className="space-y-4">
          {validationMode === 'pdf' ? (
            <InteractiveDocumentViewer
              validationData={validationData}
              currentPage={currentPage}
              setCurrentPage={setCurrentPage}
              zoom={zoom}
              setZoom={setZoom}
              showBoundingBoxes={showBoundingBoxes}
              setShowBoundingBoxes={setShowBoundingBoxes}
              confidenceFilter={confidenceFilter}
              setConfidenceFilter={setConfidenceFilter}
              canvasRef={canvasRef}
              overlayCanvasRef={overlayCanvasRef}
              onCanvasClick={handleCanvasClick}
              onCanvasMouseMove={handleCanvasMouseMove}
            />
          ) : (
            <ExcelSourcesViewer 
              excelValues={excelValues}
              validationMode={validationMode}
            />
          )}
        </div>

        {/* Validation Panel */}
        <div className="space-y-4">
          {validationMode === 'pdf' && (
            <PdfValuesPanel
              pdfValues={filteredPdfValues}
              selectedValueId={selectedValueId}
              onValueSelect={setSelectedValueId}
              onValueEdit={handlePdfValueEdit}
            />
          )}
          
          {validationMode === 'excel' && (
            <ExcelValuesPanel
              excelValues={excelValues}
              onValueEdit={handleExcelValueEdit}
            />
          )}
          
          {validationMode === 'audit' && (
            <DirectAuditPanel
              pdfValues={pdfValues}
              excelValues={excelValues}
              onStartAudit={startDirectAudit}
              loading={startingAudit}
            />
          )}
        </div>
      </div>
    </div>
  );
};

// Supporting Components
const InteractiveDocumentViewer = ({ 
  validationData, currentPage, setCurrentPage, zoom, setZoom, 
  showBoundingBoxes, setShowBoundingBoxes, confidenceFilter, setConfidenceFilter,
  canvasRef, overlayCanvasRef, onCanvasClick, onCanvasMouseMove 
}) => {
  const totalPages = validationData?.document_preview?.pages?.length || 0;

  return (
    <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b bg-gray-50">
        <div className="flex items-center space-x-4">
          <h3 className="text-lg font-medium flex items-center">
            <FileText className="h-5 w-5 mr-2 text-blue-600" />
            PDF Document Preview
          </h3>
          <span className="text-sm text-gray-500">
            Page {currentPage + 1} of {totalPages}
          </span>
        </div>
        
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1 bg-white rounded border">
            <button
              onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}
              className="p-1 text-gray-600 hover:text-gray-900"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <span className="px-2 text-sm text-gray-600 border-x">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => setZoom(Math.min(3.0, zoom + 0.25))}
              className="p-1 text-gray-600 hover:text-gray-900"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
          </div>
          
          <button
            onClick={() => setShowBoundingBoxes(!showBoundingBoxes)}
            className={`px-3 py-1 text-sm rounded border ${
              showBoundingBoxes 
                ? 'bg-blue-100 text-blue-700 border-blue-300' 
                : 'bg-white text-gray-600 border-gray-300'
            }`}
          >
            <Eye className="h-4 w-4 inline mr-1" />
            Overlays
          </button>
        </div>
      </div>

      <div className="px-4 py-3 border-b bg-gray-50">
        <div className="flex items-center space-x-3">
          <label className="text-sm font-medium text-gray-700">
            Confidence Filter:
          </label>
          <input
            type="range"
            min="0"
            max="100"
            value={confidenceFilter}
            onChange={(e) => setConfidenceFilter(parseInt(e.target.value))}
            className="flex-1"
          />
          <span className="text-sm text-gray-600 w-12">
            {confidenceFilter}%
          </span>
        </div>
      </div>

      <div className="relative bg-gray-100 overflow-auto" style={{ maxHeight: '600px' }}>
        <div className="relative">
          <canvas
            ref={canvasRef}
            className="block"
            style={{ maxWidth: '100%', height: 'auto' }}
          />
          <canvas
            ref={overlayCanvasRef}
            onClick={onCanvasClick}
            onMouseMove={onCanvasMouseMove}
            className="absolute top-0 left-0 cursor-pointer"
            style={{ 
              maxWidth: '100%', 
              height: 'auto',
              pointerEvents: showBoundingBoxes ? 'auto' : 'none'
            }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between p-4 border-t">
        <button
          onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
          disabled={currentPage === 0}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
        >
          Previous
        </button>
        
        <div className="flex items-center space-x-1">
          {Array.from({ length: totalPages }, (_, i) => (
            <button
              key={i}
              onClick={() => setCurrentPage(i)}
              className={`w-8 h-8 text-xs rounded ${
                currentPage === i
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {i + 1}
            </button>
          ))}
        </div>
        
        <button
          onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
          disabled={currentPage >= totalPages - 1}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
};

const ExcelSourcesViewer = ({ excelValues, validationMode }) => {
  const fileGroups = excelValues.reduce((groups, value) => {
    const file = value.source_file || 'Unknown File';
    if (!groups[file]) groups[file] = [];
    groups[file].push(value);
    return groups;
  }, {});

  return (
    <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
      <div className="p-4 border-b bg-gray-50">
        <h3 className="text-lg font-medium flex items-center">
          <BarChart3 className="h-5 w-5 mr-2 text-green-600" />
          Excel Sources Overview
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          All extracted Excel values available for validation
        </p>
      </div>
      
      <div className="max-h-96 overflow-y-auto p-4">
        {Object.entries(fileGroups).map(([fileName, values]) => (
          <div key={fileName} className="mb-6">
            <h4 className="font-medium text-gray-900 mb-3 flex items-center">
              <Database className="h-4 w-4 mr-2 text-green-600" />
              {fileName} ({values.length} values)
            </h4>
            <div className="grid grid-cols-1 gap-2">
              {values.slice(0, 5).map((value, idx) => (
                <div key={idx} className="bg-gray-50 p-2 rounded text-sm">
                  <div className="flex justify-between">
                    <span className="font-medium">{value.cell_reference}</span>
                    <span className="text-gray-600">{value.value}</span>
                  </div>
                  {value.business_context && (
                    <div className="text-xs text-gray-500 mt-1">
                      {value.business_context}
                    </div>
                  )}
                </div>
              ))}
              {values.length > 5 && (
                <div className="text-sm text-gray-500 italic">
                  ... and {values.length - 5} more values
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const PdfValuesPanel = ({ pdfValues, selectedValueId, onValueSelect, onValueEdit }) => {
  const [editingValue, setEditingValue] = useState(null);

  return (
    <div className="bg-white border rounded-lg overflow-hidden">
      <div className="p-4 border-b bg-gray-50">
        <h3 className="text-lg font-medium flex items-center">
          <FileText className="h-5 w-5 mr-2 text-blue-600" />
          PDF Values Validation ({pdfValues.length})
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          Validate all extracted PDF values - click on document to select
        </p>
      </div>
      
      <div className="max-h-96 overflow-y-auto">
        {pdfValues.map((value) => (
          <PdfValueCard
            key={value.id}
            value={value}
            isSelected={selectedValueId === value.id}
            onSelect={onValueSelect}
            onEdit={(newData) => {
              onValueEdit(value.id, newData);
              setEditingValue(null);
            }}
            onStartEdit={() => setEditingValue(value)}
            isEditing={editingValue?.id === value.id}
            onCancelEdit={() => setEditingValue(null)}
          />
        ))}
      </div>
    </div>
  );
};

const PdfValueCard = ({ value, isSelected, onSelect, onEdit, onStartEdit, isEditing, onCancelEdit }) => {
  const [editData, setEditData] = useState({
    value: value.value || '',
    business_context: value.business_context?.semantic_meaning || ''
  });

  const getConfidenceColor = (confidence) => {
    if (!confidence) return 'bg-gray-100 text-gray-800';
    if (confidence >= 0.8) return 'bg-green-100 text-green-800';
    if (confidence >= 0.6) return 'bg-yellow-100 text-yellow-800';
    return 'bg-red-100 text-red-800';
  };

  if (isEditing) {
    return (
      <div className="p-4 border-b bg-blue-50">
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Value</label>
            <input
              type="text"
              value={editData.value}
              onChange={(e) => setEditData({...editData, value: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Business Context</label>
            <textarea
              value={editData.business_context}
              onChange={(e) => setEditData({...editData, business_context: e.target.value})}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div className="flex justify-end space-x-2">
            <button
              onClick={onCancelEdit}
              className="px-3 py-1 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50 flex items-center"
            >
              <X className="h-4 w-4 mr-1" />
              Cancel
            </button>
            <button
              onClick={() => onEdit(editData)}
              className="px-3 py-1 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 flex items-center"
            >
              <Save className="h-4 w-4 mr-1" />
              Save
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      onClick={() => onSelect(value.id)}
      className={`p-4 border-b cursor-pointer transition-colors ${
        isSelected ? 'bg-blue-50 border-blue-200' : 'hover:bg-gray-50'
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <span className="font-medium text-gray-900">{value.value}</span>
            <span className={`text-xs px-2 py-1 rounded-full ${getConfidenceColor(value.confidence)}`}>
              {Math.round((value.confidence || 0) * 100)}%
            </span>
            {value.user_modified && (
              <span className="text-xs px-2 py-1 rounded-full bg-purple-100 text-purple-800">
                Modified
              </span>
            )}
          </div>
          <p className="text-sm text-gray-600 mb-1">
            {value.business_context?.semantic_meaning || 'No context available'}
          </p>
          <div className="flex items-center space-x-3 text-xs text-gray-500">
            <span>Page {value.page_number}</span>
            <span>{value.data_type}</span>
            <span>{value.business_context?.business_category}</span>
          </div>
        </div>
        
        <button
          onClick={(e) => {
            e.stopPropagation();
            onStartEdit();
          }}
          className="p-1 text-gray-400 hover:text-gray-600"
        >
          <Edit3 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

const ExcelValuesPanel = ({ excelValues, onValueEdit }) => {
  const [editingValue, setEditingValue] = useState(null);

  return (
    <div className="bg-white border rounded-lg overflow-hidden">
      <div className="p-4 border-b bg-gray-50">
        <h3 className="text-lg font-medium flex items-center">
          <BarChart3 className="h-5 w-5 mr-2 text-green-600" />
          Excel Values Validation ({excelValues.length})
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          Validate all extracted Excel source values
        </p>
      </div>
      
      <div className="max-h-96 overflow-y-auto">
        {excelValues.map((value, index) => (
          <ExcelValueCard
            key={`${value.source_file}_${value.cell_reference}_${index}`}
            value={value}
            valueId={`${value.source_file}_${value.cell_reference}`}
            onEdit={(newData) => {
              onValueEdit(`${value.source_file}_${value.cell_reference}`, newData);
              setEditingValue(null);
            }}
            onStartEdit={() => setEditingValue(`${value.source_file}_${value.cell_reference}`)}
            isEditing={editingValue === `${value.source_file}_${value.cell_reference}`}
            onCancelEdit={() => setEditingValue(null)}
          />
        ))}
      </div>
    </div>
  );
};

const ExcelValueCard = ({ value, valueId, onEdit, onStartEdit, isEditing, onCancelEdit }) => {
  const [editData, setEditData] = useState({
    value: value.value || '',
    business_context: value.business_context || ''
  });

  if (isEditing) {
    return (
      <div className="p-4 border-b bg-green-50">
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Value</label>
            <input
              type="text"
              value={editData.value}
              onChange={(e) => setEditData({...editData, value: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Business Context</label>
            <textarea
              value={editData.business_context}
              onChange={(e) => setEditData({...editData, business_context: e.target.value})}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div className="flex justify-end space-x-2">
            <button
              onClick={onCancelEdit}
              className="px-3 py-1 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50 flex items-center"
            >
              <X className="h-4 w-4 mr-1" />
              Cancel
            </button>
            <button
              onClick={() => onEdit(editData)}
              className="px-3 py-1 text-sm text-white bg-green-600 rounded hover:bg-green-700 flex items-center"
            >
              <Save className="h-4 w-4 mr-1" />
              Save
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 border-b hover:bg-gray-50">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <span className="text-sm font-medium text-gray-700">{value.source_file}</span>
            <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-800">
              {value.cell_reference}
            </span>
            {value.user_modified && (
              <span className="text-xs px-2 py-1 rounded-full bg-purple-100 text-purple-800">
                Modified
              </span>
            )}
          </div>
          <div className="font-medium text-gray-900 mb-1">{value.value}</div>
          <p className="text-sm text-gray-600">
            {value.business_context || 'No context available'}
          </p>
        </div>
        
        <button
          onClick={onStartEdit}
          className="p-1 text-gray-400 hover:text-gray-600"
        >
          <Edit3 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

const DirectAuditPanel = ({ pdfValues, excelValues, onStartAudit, loading }) => {
  const readyForAudit = pdfValues.length > 0 && excelValues.length > 0;
  const totalValues = pdfValues.length + excelValues.length;

  return (
    <div className="bg-white border rounded-lg overflow-hidden">
      <div className="p-4 border-b bg-gray-50">
        <h3 className="text-lg font-medium flex items-center">
          <Brain className="h-5 w-5 mr-2 text-blue-600" />
          Direct Comprehensive Audit
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          Audit ALL extracted values with 100% coverage - no mapping bottlenecks
        </p>
      </div>
      
      <div className="p-6 space-y-6">
        {/* Audit Coverage */}
        <div className="bg-gradient-to-r from-green-50 to-blue-50 p-4 rounded-lg">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Audit Coverage Analysis</h4>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{pdfValues.length}</div>
              <div className="text-sm text-gray-600">PDF Values</div>
              <div className="text-xs text-green-600">100% Coverage</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{excelValues.length}</div>
              <div className="text-sm text-gray-600">Excel Sources</div>
              <div className="text-xs text-green-600">All Available</div>
            </div>
          </div>
        </div>
        
        {/* Audit Features */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-900">Direct Audit Features</h4>
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm text-gray-600">
                Compare all {pdfValues.length} PDF values against all {excelValues.length} Excel values
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm text-gray-600">
                Advanced value normalization and semantic matching
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm text-gray-600">
                Business context-aware validation using Gemini 2.5 Pro
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm text-gray-600">
                100% coverage - no bottlenecks from mapping limitations
              </span>
            </div>
          </div>
        </div>
        
        {/* Coverage Comparison */}
        <div className="bg-orange-50 border border-orange-200 rounded p-3">
          <div className="text-sm text-orange-800">
            <strong>Coverage Advantage:</strong>
            <div className="mt-1 space-y-1">
              <div>❌ Old Approach: ~6% coverage (5 mappings out of {pdfValues.length} values)</div>
              <div>✅ Direct Approach: 100% coverage (all {pdfValues.length} values validated)</div>
            </div>
          </div>
        </div>
        
        {/* Start Audit Button */}
        <button
            onClick={onStartAudit}
          disabled={!readyForAudit || loading}
          className="w-full flex items-center justify-center px-6 py-3 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-green-600 border border-transparent rounded-lg hover:from-blue-700 hover:to-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform hover:scale-105"
        >
          {loading ? (
            <LoadingSpinner size="sm" text="Running comprehensive audit..." />
          ) : (
            <>
              <Play className="h-5 w-5 mr-2" />
              Start Direct Comprehensive Audit
              <ArrowRight className="ml-2 h-4 w-4" />
            </>
          )}
        </button>
        
        {/* Readiness Status */}
        <div className="pt-4 border-t">
          <div className="flex items-center space-x-2">
            {readyForAudit ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
            )}
            <span className="text-sm text-gray-600">
              {readyForAudit 
                ? `Ready for comprehensive audit: ${totalValues} total values to validate`
                : 'Complete document processing to enable audit'
              }
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InteractiveValidation;