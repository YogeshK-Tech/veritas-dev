import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Download, FileText, Table, BarChart3, Eye } from 'lucide-react';
import toast from 'react-hot-toast';

const ReportViewer = () => {
  const { sessionId } = useParams();
  const [reportData, setReportData] = useState(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    // For now, use mock data
    setReportData({
      sessionId,
      generatedAt: new Date().toISOString(),
      summary: {
        totalValues: 15,
        matched: 12,
        mismatched: 2,
        formattingErrors: 1,
        accuracy: 85.7
      }
    });
  }, [sessionId]);

  const generateReport = async (type) => {
    setGenerating(true);
    
    try {
      // Simulate report generation
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      toast.success(`${type} report generated successfully!`);
      
      // In a real implementation, this would download the file
      const blob = new Blob(['Mock report content'], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `veritas-${type}-report-${sessionId}.${type === 'pdf' ? 'pdf' : 'xlsx'}`;
      a.click();
      
    } catch (error) {
      toast.error('Report generation failed');
    } finally {
      setGenerating(false);
    }
  };

  if (!reportData) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Audit Reports</h1>
          <p className="text-gray-600 mb-6">
            Generate and download comprehensive reports in multiple formats
          </p>

          {/* Report Summary */}
          <div className="bg-gray-50 rounded-lg p-4 mb-6">
            <h2 className="text-lg font-medium text-gray-900 mb-3">Report Summary</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-blue-600">{reportData.summary.totalValues}</p>
                <p className="text-xs text-gray-600">Total Values</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-green-600">{reportData.summary.matched}</p>
                <p className="text-xs text-gray-600">Matched</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600">{reportData.summary.mismatched}</p>
                <p className="text-xs text-gray-600">Mismatched</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-yellow-600">{reportData.summary.formattingErrors}</p>
                <p className="text-xs text-gray-600">Format Errors</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-purple-600">{reportData.summary.accuracy}%</p>
                <p className="text-xs text-gray-600">Accuracy</p>
              </div>
            </div>
          </div>

          {/* Report Options */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Executive Summary PDF */}
            <div className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-center mb-4">
                <FileText className="h-8 w-8 text-red-500 mr-3" />
                <div>
                  <h3 className="text-lg font-medium text-gray-900">Executive Summary</h3>
                  <p className="text-sm text-gray-600">PDF format</p>
                </div>
              </div>
              <p className="text-sm text-gray-600 mb-4">
                High-level overview with key findings and recommendations for executives.
              </p>
              <button
                onClick={() => generateReport('pdf')}
                disabled={generating}
                className="w-full flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 disabled:opacity-50"
              >
                <Download className="h-4 w-4 mr-2" />
                {generating ? 'Generating...' : 'Download PDF'}
              </button>
            </div>

            {/* Detailed Excel Report */}
            <div className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-center mb-4">
                <Table className="h-8 w-8 text-green-500 mr-3" />
                <div>
                  <h3 className="text-lg font-medium text-gray-900">Detailed Analysis</h3>
                  <p className="text-sm text-gray-600">Excel format</p>
                </div>
              </div>
              <p className="text-sm text-gray-600 mb-4">
                Comprehensive data analysis with all mappings, discrepancies, and audit trail.
              </p>
              <button
                onClick={() => generateReport('excel')}
                disabled={generating}
                className="w-full flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:opacity-50"
              >
                <Download className="h-4 w-4 mr-2" />
                {generating ? 'Generating...' : 'Download Excel'}
              </button>
            </div>

            {/* Interactive Dashboard */}
            <div className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-center mb-4">
                <BarChart3 className="h-8 w-8 text-blue-500 mr-3" />
                <div>
                  <h3 className="text-lg font-medium text-gray-900">Interactive Dashboard</h3>
                  <p className="text-sm text-gray-600">Web view</p>
                </div>
              </div>
              <p className="text-sm text-gray-600 mb-4">
                Interactive charts and detailed breakdowns available in the dashboard.
              </p>
              <button
                onClick={() => window.open(`/audit/${sessionId}`, '_blank')}
                className="w-full flex items-center justify-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                <Eye className="h-4 w-4 mr-2" />
                View Dashboard
              </button>
            </div>
          </div>

          {/* Additional Information */}
          <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-blue-900 mb-2">Report Information</h3>
            <div className="text-sm text-blue-800 space-y-1">
              <p><strong>Session ID:</strong> {reportData.sessionId}</p>
              <p><strong>Generated:</strong> {new Date(reportData.generatedAt).toLocaleString()}</p>
              <p><strong>AI Engine:</strong> Google Gemini 2.5 Pro</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportViewer;