import React, { useState, useEffect } from 'react';
import { useDataCache } from '../../contexts/DataCacheContext';
import './ai_report.css';

interface AIReportData {
  status: string;
  report: {
    executive_summary: string;
    performance_metrics: string;
    issues_bottlenecks: string;
    recommendations: string;
    detailed_analysis: string;
    generated_at: string;
  };
  metadata?: {
    generated_at: string;
    data_points_analyzed?: {
      logs: number;
      jobs: number;
      gantt_priority_items: number;
      gantt_resource_items: number;
    };
    error?: string;
  };
}

const AIReport: React.FC = () => {
  const { data } = useDataCache();
  const [reportData, setReportData] = useState<AIReportData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState(false);

  // Generate AI report with streaming
  const generateReport = async () => {
    setIsLoading(true);
    setError(null);
    setReportData(null);
    setStreamingContent('');
    setIsStreaming(true);
    
    try {
      // Check if we have cached data
      if (!data.systemLogs.length && !data.detailedSchedule.length) {
        throw new Error('No cached data available. Please refresh data from the dashboard first.');
      }
      
      const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/api$/, '');
      
      // Use Server-Sent Events for streaming
      const response = await fetch(`${API_BASE_URL}/api/reports/ai-report-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          systemLogs: data.systemLogs,
          detailedSchedule: data.detailedSchedule,
          ganttPriorityView: data.ganttPriorityView,
          ganttResourceView: data.ganttResourceView,
          scheduleOverview: data.scheduleOverview
        })
      });
      
      if (!response.ok) {
        throw new Error(`Failed to generate report: ${response.status}`);
      }
      
      // Process streaming response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let completeContent = '';
      
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                
                if (data.content) {
                  // Add streaming content
                  completeContent += data.content;
                  setStreamingContent(completeContent);
                } else if (data.status === 'completed') {
                  // Streaming completed - convert to final report format
                  setIsStreaming(false);
                  setIsLoading(false);
                  
                  // Create a structured report from the complete streaming content
                  const finalReport: AIReportData = {
                    status: 'success',
                    report: {
                      executive_summary: completeContent,
                      performance_metrics: '',
                      issues_bottlenecks: '',
                      recommendations: '',
                      detailed_analysis: '',
                      generated_at: new Date().toISOString()
                    },
                    metadata: {
                      generated_at: new Date().toISOString()
                    }
                  };
                  
                  setReportData(finalReport);
                  return; // Exit the function
                } else if (data.error) {
                  throw new Error(data.error);
                }
              } catch (parseError) {
                console.warn('Failed to parse SSE data:', parseError);
              }
            }
          }
        }
        
        // If we reach here without completion signal, treat as completed
        if (completeContent) {
          setIsStreaming(false);
          setIsLoading(false);
          
          const finalReport: AIReportData = {
            status: 'success',
            report: {
              executive_summary: completeContent,
              performance_metrics: '',
              issues_bottlenecks: '',
              recommendations: '',
              detailed_analysis: '',
              generated_at: new Date().toISOString()
            },
            metadata: {
              generated_at: new Date().toISOString()
            }
          };
          
          setReportData(finalReport);
        }
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('Error generating AI report:', err);
      setIsStreaming(false);
    } finally {
      setIsLoading(false);
    }
  };

  // Auto-generate report if we have cached data
  useEffect(() => {
    if (data.systemLogs.length > 0 || data.detailedSchedule.length > 0) {
      generateReport();
    }
  }, [data.lastRefresh]);

  // Format report section content
  const formatReportSection = (content: string) => {
    if (!content) return null;
    
    return content.split('\n').map((line, index) => {
      const trimmedLine = line.trim();
      if (!trimmedLine) return <br key={index} />;
      
      // Handle bullet points
      if (trimmedLine.startsWith('- ') || trimmedLine.startsWith('" ')) {
        return (
          <li key={index} className="report-bullet">
            {trimmedLine.substring(2)}
          </li>
        );
      }
      
      // Handle numbered lists
      if (/^\d+\./.test(trimmedLine)) {
        return (
          <li key={index} className="report-numbered">
            {trimmedLine.substring(trimmedLine.indexOf('.') + 1).trim()}
          </li>
        );
      }
      
      return <p key={index} className="report-paragraph">{trimmedLine}</p>;
    });
  };

  // Get status badge
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return <span className="status-badge status-success">AI Generated</span>;
      case 'fallback':
        return <span className="status-badge status-fallback">Basic Analysis</span>;
      case 'error':
        return <span className="status-badge status-error">Error</span>;
      default:
        return <span className="status-badge status-unknown">Unknown</span>;
    }
  };

  return (
    <div className="ai-report-container">
      <div className="ai-report-header">
        <button 
          className="back-button" 
          onClick={() => window.history.back()}
        >
          <i className="fas fa-arrow-left"></i> Back
        </button>
        <h1>AI Production Report</h1>
        <button 
          className="generate-button" 
          onClick={generateReport}
          disabled={isLoading}
        >
          <i className={`fas fa-${isLoading ? 'spinner fa-spin' : 'brain'}`}></i>
          {isLoading ? 'Generating...' : 'Generate New Report'}
        </button>
      </div>

      <div className="ai-report-content">
        {error && (
          <div className="error-message">
            <i className="fas fa-exclamation-triangle"></i>
            <span>Error: {error}</span>
          </div>
        )}

        {isLoading && (
          <div className="loading-container">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
            <p>Analyzing data and generating AI report...</p>
          </div>
        )}

        {isStreaming && streamingContent && (
          <div className="streaming-container">
            <div className="streaming-header">
              <h3>🤖 AI Analysis in Progress...</h3>
              <div className="streaming-indicator">
                <span className="streaming-dot"></span>
                <span className="streaming-dot"></span>
                <span className="streaming-dot"></span>
              </div>
            </div>
            <div className="streaming-content">
              <pre className="streaming-text">{streamingContent}</pre>
            </div>
          </div>
        )}

        {reportData && !isLoading && (
          <div className="report-sections">
            {/* Report Header */}
            <div className="report-meta">
              <div className="report-status">
                {getStatusBadge(reportData.status)}
                <span className="generated-time">
                  Generated: {new Date(reportData.report.generated_at).toLocaleString()}
                </span>
              </div>
              
              {reportData.metadata?.data_points_analyzed && (
                <div className="data-points">
                  <span>Data Points: </span>
                  <span>{reportData.metadata.data_points_analyzed.logs} logs, </span>
                  <span>{reportData.metadata.data_points_analyzed.jobs} jobs, </span>
                  <span>{reportData.metadata.data_points_analyzed.gantt_priority_items + reportData.metadata.data_points_analyzed.gantt_resource_items} gantt items</span>
                </div>
              )}
            </div>

            {/* Executive Summary */}
            <section className="report-section">
              <h2 className="section-title">
                <i className="fas fa-chart-line"></i>
                Executive Summary
              </h2>
              <div className="section-content">
                {formatReportSection(reportData.report.executive_summary)}
              </div>
            </section>

            {/* Performance Metrics */}
            <section className="report-section">
              <h2 className="section-title">
                <i className="fas fa-tachometer-alt"></i>
                Performance Metrics
              </h2>
              <div className="section-content">
                {formatReportSection(reportData.report.performance_metrics)}
              </div>
            </section>

            {/* Issues & Bottlenecks */}
            <section className="report-section">
              <h2 className="section-title">
                <i className="fas fa-exclamation-circle"></i>
                Issues & Bottlenecks
              </h2>
              <div className="section-content">
                {formatReportSection(reportData.report.issues_bottlenecks)}
              </div>
            </section>

            {/* Recommendations */}
            <section className="report-section">
              <h2 className="section-title">
                <i className="fas fa-lightbulb"></i>
                Recommendations
              </h2>
              <div className="section-content">
                {formatReportSection(reportData.report.recommendations)}
              </div>
            </section>

            {/* Detailed Analysis */}
            <section className="report-section">
              <h2 className="section-title">
                <i className="fas fa-microscope"></i>
                Detailed Analysis
              </h2>
              <div className="section-content">
                {formatReportSection(reportData.report.detailed_analysis)}
              </div>
            </section>
          </div>
        )}

        {!reportData && !isLoading && !error && (
          <div className="no-report">
            <i className="fas fa-robot"></i>
            <h3>No AI Report Available</h3>
            {data.systemLogs.length === 0 && data.detailedSchedule.length === 0 ? (
              <p>No cached data available. Please go to the dashboard and click "Refresh All Data" first, then return here to generate an AI report.</p>
            ) : (
              <p>Click "Generate New Report" to create an AI-powered analysis of your production scheduling data.</p>
            )}
            <button 
              className="generate-button-large" 
              onClick={generateReport}
              disabled={data.systemLogs.length === 0 && data.detailedSchedule.length === 0}
            >
              <i className="fas fa-brain"></i>
              Generate AI Report
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default AIReport;