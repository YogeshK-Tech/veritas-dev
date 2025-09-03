import React, { useState, useEffect } from 'react';
import { Bar } from 'react-chartjs-2';
import { Clock, DollarSign, Cpu, AlertCircle } from 'lucide-react';
import { apiService } from '../../services/api';

const MetricsPanel = ({ sessionId }) => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMetrics();
  }, [sessionId]);

  const loadMetrics = async () => {
    try {
      const stats = await apiService.getStats();
      
      // Mock detailed metrics for now
      setMetrics({
        processing_time: 2.3,
        ai_tokens_used: 1250,
        estimated_cost: 0.05,
        operations: [
          { name: 'Upload', duration: 0.5, success: true },
          { name: 'PDF Processing', duration: 1.2, success: true },
          { name: 'Excel Processing', duration: 0.8, success: true },
          { name: 'AI Mapping', duration: 2.1, success: true },
          { name: 'Audit Validation', duration: 1.7, success: true }
        ],
        performance_data: {
          labels: ['Upload', 'Processing', 'AI Analysis', 'Validation'],
          datasets: [{
            label: 'Duration (seconds)',
            data: [0.5, 1.0, 2.1, 1.7],
            backgroundColor: ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B'],
          }]
        }
      });
      
    } catch (error) {
      console.error('Failed to load metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gray-200 h-20 rounded-lg"></div>
          ))}
        </div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="text-center py-8">
        <AlertCircle className="mx-auto h-12 w-12 text-gray-400" />
        <p className="mt-2 text-gray-500">Unable to load metrics</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-blue-50 p-4 rounded-lg">
          <div className="flex items-center">
            <Clock className="h-6 w-6 text-blue-500 mr-2" />
            <div>
              <p className="text-sm font-medium text-blue-600">Processing Time</p>
              <p className="text-xl font-bold text-blue-900">{metrics.processing_time}s</p>
            </div>
          </div>
        </div>

        <div className="bg-green-50 p-4 rounded-lg">
          <div className="flex items-center">
            <Cpu className="h-6 w-6 text-green-500 mr-2" />
            <div>
              <p className="text-sm font-medium text-green-600">AI Tokens Used</p>
              <p className="text-xl font-bold text-green-900">{metrics.ai_tokens_used.toLocaleString()}</p>
            </div>
          </div>
        </div>

        <div className="bg-purple-50 p-4 rounded-lg">
          <div className="flex items-center">
            <DollarSign className="h-6 w-6 text-purple-500 mr-2" />
            <div>
              <p className="text-sm font-medium text-purple-600">Estimated Cost</p>
              <p className="text-xl font-bold text-purple-900">${metrics.estimated_cost}</p>
            </div>
          </div>
        </div>

        <div className="bg-yellow-50 p-4 rounded-lg">
          <div className="flex items-center">
            <AlertCircle className="h-6 w-6 text-yellow-500 mr-2" />
            <div>
              <p className="text-sm font-medium text-yellow-600">Success Rate</p>
              <p className="text-xl font-bold text-yellow-900">100%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Performance Chart */}
      <div className="bg-gray-50 p-6 rounded-lg">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Operation Performance</h3>
        <div className="h-64">
          <Bar
            data={metrics.performance_data}
            options={{
              responsive: true,
              maintainAspectRatio: false,
              scales: {
                y: {
                  beginAtZero: true,
                  title: {
                    display: true,
                    text: 'Duration (seconds)'
                  }
                }
              }
            }}
          />
        </div>
      </div>

      {/* Operations Timeline */}
      <div className="bg-white border rounded-lg p-4">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Operations Timeline</h3>
        <div className="space-y-2">
          {metrics.operations.map((operation, index) => (
            <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
              <div className="flex items-center">
                <div className={`h-2 w-2 rounded-full mr-3 ${operation.success ? 'bg-green-500' : 'bg-red-500'}`}></div>
                <span className="text-sm font-medium">{operation.name}</span>
              </div>
              <span className="text-sm text-gray-600">{operation.duration}s</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default MetricsPanel;