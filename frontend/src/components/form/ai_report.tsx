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
    raw_content?: string;
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
                } else if (data.status === 'completed' || data.status === 'success') {
                  // Streaming completed - use the structured report if available
                  setIsStreaming(false);
                  setIsLoading(false);
                  
                  if (data.report) {
                    // Use the structured report from backend
                    setReportData(data);
                  } else {
                    // Fallback to complete content
                    const finalReport: AIReportData = {
                      status: 'success',
                      report: {
                        executive_summary: completeContent,
                        performance_metrics: '',
                        issues_bottlenecks: '',
                        recommendations: '',
                        detailed_analysis: '',
                        generated_at: new Date().toISOString(),
                        raw_content: completeContent
                      },
                      metadata: {
                        generated_at: new Date().toISOString()
                      }
                    };
                    setReportData(finalReport);
                  }
                  return;
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
              generated_at: new Date().toISOString(),
              raw_content: completeContent
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

  // Format report section content with enhanced styling
  const formatReportSection = (content: string) => {
    if (!content) return null;
    
    const lines = content.split('\n');
    const elements: JSX.Element[] = [];
    let listItems: string[] = [];
    let listType: 'bullet' | 'numbered' | null = null;
    
    const flushList = () => {
      if (listItems.length > 0) {
        if (listType === 'numbered') {
          elements.push(
            <ol key={`list-${elements.length}`} className="report-list">
              {listItems.map((item, idx) => (
                <li key={idx} className="report-list-item">{item}</li>
              ))}
            </ol>
          );
        } else {
          elements.push(
            <ul key={`list-${elements.length}`} className="report-list">
              {listItems.map((item, idx) => (
                <li key={idx} className="report-list-item">{item}</li>
              ))}
            </ul>
          );
        }
        listItems = [];
        listType = null;
      }
    };
    
    lines.forEach((line, index) => {
      const trimmedLine = line.trim();
      if (!trimmedLine) {
        flushList();
        return;
      }
      
      // Handle headers
      if (trimmedLine.startsWith('###') || trimmedLine.includes('**') && trimmedLine.length < 100) {
        flushList();
        const headerText = trimmedLine.replace(/[#*]/g, '').trim();
        elements.push(
          <h4 key={index} className="report-subheader">{headerText}</h4>
        );
        return;
      }
      
      // Handle bullet points
      if (trimmedLine.startsWith('- ') || trimmedLine.startsWith('• ')) {
        if (listType !== 'bullet') {
          flushList();
          listType = 'bullet';
        }
        listItems.push(trimmedLine.substring(2));
        return;
      }
      
      // Handle numbered lists
      if (/^\d+\./.test(trimmedLine)) {
        if (listType !== 'numbered') {
          flushList();
          listType = 'numbered';
        }
        listItems.push(trimmedLine.substring(trimmedLine.indexOf('.') + 1).trim());
        return;
      }
      
      // Handle paragraphs
      flushList();
      elements.push(
        <p key={index} className="report-paragraph">{trimmedLine}</p>
      );
    });
    
    flushList();
    return elements;
  };

  // Get status badge
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return <span className="status-badge status-success">🤖 AI Generated</span>;
      case 'fallback':
        return <span className="status-badge status-fallback">📊 Basic Analysis</span>;
      case 'error':
        return <span className="status-badge status-error">❌ Error</span>;
      default:
        return <span className="status-badge status-unknown">❓ Unknown</span>;
    }
  };

  // Calculate metrics for dashboard
  const getMetrics = () => {
    if (!reportData?.metadata?.data_points_analyzed) return null;
    
    const { logs, jobs, gantt_priority_items, gantt_resource_items } = reportData.metadata.data_points_analyzed;
    const errorLogs = data.systemLogs.filter(log => log.level === 'ERROR').length;
    const warningLogs = data.systemLogs.filter(log => log.level === 'WARNING').length;
    const completedJobs = data.detailedSchedule.filter(job => job.status === 'completed').length;
    const completionRate = jobs > 0 ? (completedJobs / jobs * 100) : 0;
    
    return {
      totalJobs: jobs,
      completionRate,
      errorLogs,
      warningLogs,
      totalGanttItems: gantt_priority_items + gantt_resource_items
    };
  };

  const metrics = getMetrics();

  return (
    <div className="ai-report-container">
      {/* Header */}
      <div className="ai-report-header">
        <h1>🤖 AI Production Report</h1>
        <div className="header-actions">
          <button 
            className="back-button" 
            onClick={() => window.history.back()}
          >
            <i className="fas fa-arrow-left"></i> Back
          </button>
          <button 
            className="generate-button" 
            onClick={generateReport}
            disabled={isLoading}
          >
            <i className={`fas fa-${isLoading ? 'spinner fa-spin' : 'brain'}`}></i>
            {isLoading ? 'Generating...' : 'Generate New Report'}
          </button>
        </div>
      </div>

      <div className="ai-report-content">
        {/* Error Message */}
        {error && (
          <div className="alert-box error-alert">
            <h3><span className="alert-icon">🚨</span>Error</h3>
            <p>{error}</p>
          </div>
        )}

        {/* Loading State */}
        {isLoading && !isStreaming && (
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <p>🔍 Analyzing data and generating AI report...</p>
          </div>
        )}

        {/* Streaming State */}
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
              <div className="streaming-text">{streamingContent}</div>
            </div>
          </div>
        )}

        {/* Report Content */}
        {reportData && !isLoading && (
          <div className="report-container">
            {/* Report Header with Metrics */}
            <div className="report-header">
              <div className="report-status">
                {getStatusBadge(reportData.status)}
                <span className="generated-time">
                  Generated: {new Date(reportData.report.generated_at).toLocaleString()}
                </span>
              </div>
              
              {/* Key Metrics Dashboard */}
              {metrics && (
                <div className="metrics-dashboard">
                  <div className="metric-card">
                    <div className={`metric-value ${metrics.completionRate === 0 ? 'critical' : metrics.completionRate < 50 ? 'warning' : 'ok'}`}>
                      {metrics.completionRate.toFixed(1)}%
                    </div>
                    <div className="metric-label">Completion Rate</div>
                    <small>{metrics.totalJobs} total jobs</small>
                  </div>
                  <div className="metric-card">
                    <div className={`metric-value ${metrics.errorLogs > 10 ? 'critical' : metrics.errorLogs > 0 ? 'warning' : 'ok'}`}>
                      {metrics.errorLogs}
                    </div>
                    <div className="metric-label">System Errors</div>
                  </div>
                  <div className="metric-card">
                    <div className={`metric-value ${metrics.warningLogs > 20 ? 'warning' : 'ok'}`}>
                      {metrics.warningLogs}
                    </div>
                    <div className="metric-label">Warnings</div>
                  </div>
                  <div className="metric-card">
                    <div className="metric-value ok">
                      {reportData.metadata?.data_points_analyzed?.logs || 0}
                    </div>
                    <div className="metric-label">Log Entries</div>
                  </div>
                </div>
              )}
            </div>

            {/* Report Sections */}
            <div className="report-sections">
              {/* Executive Summary */}
              {reportData.report.executive_summary && (
                <section className="report-section">
                  <h2 className="section-title">
                    <i className="fas fa-chart-line"></i>
                    📊 Executive Summary
                  </h2>
                  <div className="section-content">
                    {formatReportSection(reportData.report.executive_summary)}
                  </div>
                </section>
              )}

              {/* Performance Metrics */}
              {reportData.report.performance_metrics && (
                <section className="report-section">
                  <h2 className="section-title">
                    <i className="fas fa-tachometer-alt"></i>
                    📈 Performance Metrics
                  </h2>
                  <div className="section-content">
                    {formatReportSection(reportData.report.performance_metrics)}
                  </div>
                </section>
              )}

              {/* Issues & Bottlenecks */}
              {reportData.report.issues_bottlenecks && (
                <section className="report-section">
                  <h2 className="section-title">
                    <i className="fas fa-exclamation-triangle"></i>
                    ⚠️ Issues & Bottlenecks
                  </h2>
                  <div className="section-content">
                    {formatReportSection(reportData.report.issues_bottlenecks)}
                  </div>
                </section>
              )}

              {/* Recommendations */}
              {reportData.report.recommendations && (
                <section className="report-section recommendations-section">
                  <h2 className="section-title">
                    <i className="fas fa-lightbulb"></i>
                    💡 Recommendations
                  </h2>
                  <div className="section-content">
                    {formatReportSection(reportData.report.recommendations)}
                  </div>
                </section>
              )}

              {/* Detailed Analysis */}
              {reportData.report.detailed_analysis && (
                <section className="report-section">
                  <h2 className="section-title">
                    <i className="fas fa-microscope"></i>
                    🔍 Detailed Analysis
                  </h2>
                  <div className="section-content">
                    {formatReportSection(reportData.report.detailed_analysis)}
                  </div>
                </section>
              )}

              {/* Raw Content (if no structured sections) */}
              {reportData.report.raw_content && 
               !reportData.report.performance_metrics && 
               !reportData.report.issues_bottlenecks && (
                <section className="report-section">
                  <h2 className="section-title">
                    <i className="fas fa-file-alt"></i>
                    📄 Complete Analysis
                  </h2>
                  <div className="section-content">
                    {formatReportSection(reportData.report.raw_content)}
                  </div>
                </section>
              )}
            </div>
          </div>
        )}

        {/* No Report State */}
        {!reportData && !isLoading && !error && (
          <div className="no-report">
            <i className="fas fa-robot report-icon"></i>
            <h3>No AI Report Available</h3>
            {data.systemLogs.length === 0 && data.detailedSchedule.length === 0 ? (
              <p>No cached data available. Please go to the dashboard and click "Refresh All Data" first, then return here to generate an AI report.</p>
            ) : (
              <p>Click "Generate New Report" to create an AI-powered analysis of your production scheduling data using DeepSeek AI.</p>
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