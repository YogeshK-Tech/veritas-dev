import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { Upload, FileText, Table, X, CheckCircle, ArrowRight } from 'lucide-react';

import { apiService } from '../../services/api';
import LoadingSpinner from '../Common/LoadingSpinner';

const FileUpload = () => {
  const navigate = useNavigate();
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [sessionId, setSessionId] = useState(null);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls']
    },
    onDrop: async (acceptedFiles) => {
      await handleFileUpload(acceptedFiles);
    }
  });

  const handleFileUpload = async (files) => {
    if (files.length === 0) return;

    // Validate file types
    const pdfFiles = files.filter(f => f.type === 'application/pdf');
    const excelFiles = files.filter(f => 
      f.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
      f.type === 'application/vnd.ms-excel'
    );

    if (pdfFiles.length !== 1) {
      toast.error('Please upload exactly one PDF file');
      return;
    }

    if (excelFiles.length === 0) {
      toast.error('Please upload at least one Excel file');
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();
      files.forEach(file => {
        formData.append('files', file);
      });

      const response = await apiService.uploadDocuments(formData);
      
      setUploadedFiles(response.documents);
      setSessionId(response.session_id);
      toast.success(`Successfully uploaded ${response.documents.length} files!`);

    } catch (error) {
      console.error('Upload failed:', error);
      toast.error('Upload failed: ' + error.message);
    } finally {
      setUploading(false);
    }
  };

  const removeFile = (fileId) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const startProcessing = async () => {
    if (!sessionId || uploadedFiles.length === 0) {
      toast.error('Please upload files first');
      return;
    }

    setProcessing(true);

    try {
    // Step 1: Process documents
    const processResponse = await apiService.processDocuments(sessionId);
    console.log('Process response:', processResponse);
    
    if (!processResponse.overall_success) {
      throw new Error('Document processing failed');
    }

    toast.success('Documents processed successfully!');

    // Step 2: Generate AI mapping suggestions
    const mappingResponse = await apiService.suggestMappings(sessionId);
    console.log('Mapping response:', mappingResponse);
    
    // Check if we got mappings
    const suggestions = mappingResponse.mapping_suggestions?.suggested_mappings || [];
    console.log('Mapping suggestions count:', suggestions.length);
    
    if (suggestions.length === 0) {
      toast.error('No mappings generated. Please check if your documents contain financial data.');
      return;
    }
    
    toast.success(`Generated ${suggestions.length} mapping suggestions!`);
    
    // Navigate to mapping confirmation
    navigate(`/mapping/${sessionId}`, {
      state: {
        sessionId: sessionId,
        mappingSuggestions: mappingResponse.mapping_suggestions,
        pdfDocument: mappingResponse.pdf_document,
        excelDocuments: mappingResponse.excel_documents
      }
    });

  } catch (error) {
    console.error('Processing failed:', error);
    toast.error('Processing failed: ' + error.message);
  } finally {
    setProcessing(false);
  }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900">Veritas AI Auditor</h1>
        <p className="mt-2 text-lg text-gray-600">
          Upload your presentation and source spreadsheets for automated validation
        </p>
      </div>

      {/* Upload Zone */}
      <div
        {...getRootProps()}
        className={`relative border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        } ${uploading ? 'pointer-events-none opacity-50' : ''}`}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <LoadingSpinner size="lg" text="Uploading files..." />
        ) : (
          <>
            <Upload className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-lg font-medium text-gray-900">
              {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
            </p>
            <p className="mt-1 text-sm text-gray-500">
              or click to select files
            </p>
          </>
        )}
        <p className="mt-2 text-xs text-gray-400">
          Supported: PDF presentations, Excel spreadsheets (.xlsx, .xls)
        </p>
      </div>

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
              Uploaded Files ({uploadedFiles.length})
            </h3>
            
            <div className="space-y-3">
              {uploadedFiles.map((file) => (
                <div key={file.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center space-x-3">
                    {file.document_type === 'pdf' ? (
                      <FileText className="h-8 w-8 text-red-500" />
                    ) : (
                      <Table className="h-8 w-8 text-green-500" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-gray-900">{file.filename}</p>
                      <p className="text-xs text-gray-500">
                        {(file.file_size / 1024 / 1024).toFixed(2)} MB • {file.document_type.toUpperCase()}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="h-5 w-5 text-green-500" />
                    <button
                      onClick={() => removeFile(file.id)}
                      className="text-gray-400 hover:text-red-500"
                      disabled={processing}
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      {uploadedFiles.length > 0 && (
        <div className="flex justify-center space-x-4">
          <button
            onClick={() => {
              setUploadedFiles([]);
              setSessionId(null);
            }}
            disabled={processing}
            className="px-6 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Clear All
          </button>
          
          <button
            onClick={startProcessing}
            disabled={processing || uploading}
            className="px-6 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {processing ? (
              <LoadingSpinner size="sm" text="Processing..." className="mr-2" />
            ) : (
              <>
                Process & Generate Mappings
                <ArrowRight className="ml-2 h-4 w-4" />
              </>
            )}
          </button>
        </div>
      )}

      {/* Instructions */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-medium text-blue-900 mb-2">How it works:</h3>
        <ol className="list-decimal list-inside space-y-1 text-sm text-blue-800">
          <li>Upload one PDF presentation and one or more Excel source files</li>
          <li>AI will extract and analyze data from both document types</li>
          <li>Review and confirm suggested data mappings</li>
          <li>Run comprehensive audit to identify discrepancies</li>
          <li>Generate detailed reports with actionable insights</li>
        </ol>
      </div>
    </div>
  );
};

export default FileUpload;