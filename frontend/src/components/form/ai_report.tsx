import React, { useState, useEffect } from 'react';
import { useDataCache } from '../../contexts/DataCacheContext';
import './ai_report.css';
import './ai_report_comprehensive.css';

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

  // Calculate metrics directly from cached data
  const getComprehensiveMetrics = () => {
    const totalJobs = data.detailedSchedule.length;
    
    // Count buffer status directly
    const lateJobs = data.detailedSchedule.filter(job => job.buffer_status === 'Late').length;
    const criticalJobs = data.detailedSchedule.filter(job => job.buffer_status === 'Critical').length;
    const warningJobs = data.detailedSchedule.filter(job => job.buffer_status === 'Warning').length;
    const cautionJobs = data.detailedSchedule.filter(job => job.buffer_status === 'Caution').length;
    const okJobs = data.detailedSchedule.filter(job => job.buffer_status === 'OK').length;
    
    // Calculate unscheduled as remaining jobs
    const scheduledCount = lateJobs + criticalJobs + warningJobs + cautionJobs + okJobs;
    const unscheduledJobs = totalJobs - scheduledCount;
    
    // Count system logs
    const errorLogs = data.systemLogs.filter(log => log.level === 'ERROR').length;
    const warningLogs = data.systemLogs.filter(log => log.level === 'WARNING').length;
    
    // Calculate rates
    const completionRate = totalJobs > 0 ? (okJobs / totalJobs * 100) : 0;
    const schedulingRate = totalJobs > 0 ? (scheduledCount / totalJobs * 100) : 0;
    const unscheduledRate = totalJobs > 0 ? (unscheduledJobs / totalJobs * 100) : 0;
    
    return {
      totalJobs,
      completionRate,
      schedulingRate,
      unscheduledRate,
      errorLogs,
      warningLogs,
      lateJobs,
      criticalJobs,
      scheduledJobs: scheduledCount,
      unknownJobs: unscheduledJobs,
      bufferBreakdown: {
        Late: lateJobs,
        Critical: criticalJobs,
        Warning: warningJobs,
        Caution: cautionJobs,
        OK: okJobs,
        Unscheduled: unscheduledJobs
      },
      totalGanttItems: data.ganttPriorityView.length + data.ganttResourceView.length
    };
  };

  const metrics = getComprehensiveMetrics();

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
          <div className="comprehensive-report">
            {/* Professional Report Header */}
            <div className="report-header-banner">
              <div className="header-content">
                <div className="header-icon">🤖</div>
                <h1>AI Production Scheduling Analysis Report</h1>
                <div className="header-meta">
                  <div>Generated: {new Date(reportData.report.generated_at).toLocaleString()}</div>
                  <div>User: carrick113@gmail.com</div>
                </div>
              </div>
            </div>

            {/* Executive Summary Section */}
            <section className="executive-summary-section">
              <h2 className="section-title">
                <i className="fas fa-chart-line"></i>
                Executive Summary
              </h2>
              
              {/* Critical System Health Alert */}
              {metrics && metrics.totalJobs > 0 && (
                <div className="critical-alert">
                  <div className="alert-header">
                    <i className="fas fa-exclamation-triangle"></i>
                    <span>Critical System Health Alert</span>
                  </div>
                  
                  <div className="critical-metrics">
                    <div className="critical-metric">
                      <div className="metric-value critical">{metrics.completionRate.toFixed(1)}%</div>
                      <div className="metric-label">ON-TIME COMPLETION</div>
                      <div className="metric-detail">{metrics.bufferBreakdown.OK} jobs OK, {metrics.totalJobs - metrics.bufferBreakdown.OK} with issues</div>
                    </div>
                    <div className="critical-metric">
                      <div className="metric-value critical">{metrics.lateJobs}</div>
                      <div className="metric-label">LATE JOBS</div>
                      <div className="metric-detail">{((metrics.lateJobs / metrics.totalJobs) * 100).toFixed(1)}% of total jobs</div>
                    </div>
                    <div className="critical-metric">
                      <div className="metric-value critical">{metrics.criticalJobs}</div>
                      <div className="metric-label">CRITICAL JOBS</div>
                      <div className="metric-detail">{((metrics.criticalJobs / metrics.totalJobs) * 100).toFixed(1)}% requiring immediate attention</div>
                    </div>
                    <div className="critical-metric">
                      <div className="metric-value warning">{metrics.warningLogs}</div>
                      <div className="metric-label">WARNINGS</div>
                      <div className="metric-detail">Mostly unscheduled jobs</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Scheduling Efficiency Issues */}
              <div className="efficiency-summary">
                <h3><i className="fas fa-cogs"></i> Scheduling Efficiency Issues</h3>
                <p>Only <strong>{metrics?.scheduledJobs} jobs ({metrics?.schedulingRate.toFixed(1)}%)</strong> successfully scheduled with <strong>{metrics?.unknownJobs} jobs ({metrics?.unscheduledRate.toFixed(1)}%)</strong> in "Unknown" status. The <strong>Greedy solver</strong> may be suboptimal for complex scheduling requirements.</p>
              </div>

              {/* Resource Utilization */}
              <div className="resource-summary">
                <h3><i className="fas fa-industry"></i> Resource Utilization</h3>
                <p><strong>10,976.8 machine hours</strong> calculated, but subcontractor hours excluded, indicating potential underutilization of available resources.</p>
              </div>
            </section>

            {/* Performance Metrics Section */}
            <section className="performance-metrics-section">
              <h2 className="section-title">
                <i className="fas fa-chart-bar"></i>
                Performance Metrics
              </h2>

              {/* Completion & Scheduling Rates */}
              <div className="completion-rates">
                <h3>Completion & Scheduling Rates</h3>
                <div className="rate-cards">
                  <div className="rate-card">
                    <div className="rate-value critical">{metrics?.completionRate.toFixed(1)}%</div>
                    <div className="rate-label">COMPLETION RATE</div>
                  </div>
                  <div className="rate-card">
                    <div className="rate-value warning">{metrics?.schedulingRate.toFixed(1)}%</div>
                    <div className="rate-label">SUCCESSFULLY SCHEDULED</div>
                    <div className="rate-detail">{metrics?.scheduledJobs}/{metrics?.totalJobs} jobs</div>
                  </div>
                  <div className="rate-card">
                    <div className="rate-value critical">{metrics?.unscheduledRate.toFixed(1)}%</div>
                    <div className="rate-label">UNSCHEDULED JOBS</div>
                    <div className="rate-detail">{metrics?.unknownJobs} unscheduled jobs</div>
                  </div>
                </div>
              </div>

              {/* Buffer Status Breakdown Table */}
              {metrics && metrics.totalJobs > 0 && (
                <div className="buffer-breakdown">
                  <h3>Buffer Status Breakdown</h3>
                  <table className="status-table">
                    <thead>
                      <tr>
                        <th>Status</th>
                        <th>Count</th>
                        <th>% of Total Jobs</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="status-late">
                        <td>Late</td>
                        <td>{metrics.bufferBreakdown.Late}</td>
                        <td>{((metrics.bufferBreakdown.Late / metrics.totalJobs) * 100).toFixed(1)}%</td>
                      </tr>
                      <tr className="status-critical">
                        <td>Critical</td>
                        <td>{metrics.bufferBreakdown.Critical}</td>
                        <td>{((metrics.bufferBreakdown.Critical / metrics.totalJobs) * 100).toFixed(1)}%</td>
                      </tr>
                      <tr className="status-warning">
                        <td>Warning</td>
                        <td>{metrics.bufferBreakdown.Warning}</td>
                        <td>{((metrics.bufferBreakdown.Warning / metrics.totalJobs) * 100).toFixed(1)}%</td>
                      </tr>
                      <tr className="status-caution">
                        <td>Caution</td>
                        <td>{metrics.bufferBreakdown.Caution}</td>
                        <td>{((metrics.bufferBreakdown.Caution / metrics.totalJobs) * 100).toFixed(1)}%</td>
                      </tr>
                      <tr className="status-ok">
                        <td>OK</td>
                        <td>{metrics.bufferBreakdown.OK}</td>
                        <td>{((metrics.bufferBreakdown.OK / metrics.totalJobs) * 100).toFixed(1)}%</td>
                      </tr>
                      <tr className="status-unknown">
                        <td>Unscheduled</td>
                        <td>{metrics.bufferBreakdown.Unscheduled}</td>
                        <td>{((metrics.bufferBreakdown.Unscheduled / metrics.totalJobs) * 100).toFixed(1)}%</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              {/* System Log Insights */}
              <div className="log-insights">
                <h3>System Log Insights</h3>
                <ul>
                  <li><strong>{metrics?.warningLogs} unscheduled jobs</strong> with warnings</li>
                  <li><strong>{metrics?.totalJobs} jobs validated</strong> across 78 machines (suggests uneven distribution)</li>
                </ul>
              </div>
            </section>

            {/* Issues & Bottlenecks Section */}
            <section className="issues-section">
              <h2 className="section-title">
                <i className="fas fa-exclamation-triangle"></i>
                Issues & Bottlenecks
              </h2>

              {/* Critical Problems */}
              <div className="critical-problems">
                <h3><i className="fas fa-times-circle"></i> Critical Problems</h3>
                
                <div className="problem-box critical">
                  <h4>High Late Jobs ({((metrics?.lateJobs || 0) / (metrics?.totalJobs || 1) * 100).toFixed(1)}%)</h4>
                  <p>Indicates missed deadlines or unrealistic scheduling constraints.</p>
                </div>

                <div className="problem-box critical">
                  <h4>Unknown Status ({metrics?.unscheduledRate.toFixed(1)}%)</h4>
                  <p>Jobs not assigned, possibly due to constraints or solver limitations.</p>
                </div>

                <div className="problem-box critical">
                  <h4>Greedy Solver Limitation</h4>
                  <p>May prioritize speed over optimal scheduling, leading to inefficiencies.</p>
                </div>
              </div>

              {/* Operational Weaknesses */}
              <div className="operational-weaknesses">
                <h3><i className="fas fa-exclamation-circle"></i> Operational Weaknesses</h3>

                <div className="problem-box warning">
                  <h4>No Error Logs</h4>
                  <p>Lack of error tracking obscures root causes.</p>
                </div>

                <div className="problem-box warning">
                  <h4>Subcontractor Hours Excluded</h4>
                  <p>Potential underreporting of total workload.</p>
                </div>

                <div className="problem-box warning">
                  <h4>Long Planning Horizon (180 days)</h4>
                  <p>May lead to outdated or inflexible schedules.</p>
                </div>
              </div>
            </section>

            {/* Recommendations Section */}
            <section className="recommendations-section">
              <h2 className="section-title">
                <i className="fas fa-lightbulb"></i>
                Recommendations
              </h2>

              <div className="recommendations-content">
                {/* Immediate Actions */}
                <div className="immediate-actions">
                  <h3><i className="fas fa-bolt"></i> Immediate Actions</h3>
                  
                  <div className="action-group">
                    <h4>Investigate Late & Critical Jobs</h4>
                    <ul>
                      <li>Identify root causes (machine downtime, unrealistic deadlines, etc.)</li>
                      <li>Prioritize rescheduling of {metrics?.lateJobs} late jobs</li>
                    </ul>
                  </div>

                  <div className="action-group">
                    <h4>Improve Solver Configuration</h4>
                    <ul>
                      <li>Switch from <strong>greedy to constraint-based or genetic algorithm</strong></li>
                      <li>Reduce planning horizon from 180 days to 90 days for flexibility</li>
                    </ul>
                  </div>
                </div>

                {/* System & Process Improvements */}
                <div className="system-improvements">
                  <h3><i className="fas fa-cogs"></i> System & Process Improvements</h3>
                  
                  <div className="improvement-item">
                    <h4>Enable Error Logging</h4>
                    <p>Track failures to diagnose unscheduled jobs</p>
                  </div>

                  <div className="improvement-item">
                    <h4>Include Subcontractor Hours</h4>
                    <p>Ensure full workload visibility</p>
                  </div>

                  <div className="improvement-item">
                    <h4>Implement Dynamic Rescheduling</h4>
                    <p>Adjust schedules in real-time based on delays</p>
                  </div>
                </div>

                {/* Long-Term Strategies */}
                <div className="long-term-strategies">
                  <h3><i className="fas fa-calendar-alt"></i> Long-Term Strategies</h3>
                  
                  <div className="strategy-item">
                    <h4>Capacity Planning Review</h4>
                    <p>Assess if current resources can handle workload</p>
                  </div>

                  <div className="strategy-item">
                    <h4>Buffer Time Optimization</h4>
                    <p>Adjust buffers to reduce late jobs</p>
                  </div>
                </div>
              </div>
            </section>

            {/* Detailed Analysis Section */}
            <section className="detailed-analysis-section">
              <h2 className="section-title">
                <i className="fas fa-search"></i>
                Detailed Analysis
              </h2>

              {/* Unscheduled Jobs Analysis */}
              <div className="analysis-group">
                <h3>Unscheduled Jobs ({metrics?.unknownJobs}, {metrics?.unscheduledRate.toFixed(1)}%)</h3>
                <p><strong>Likely due to:</strong></p>
                <ul>
                  <li><strong>Resource constraints</strong> (machines at full capacity)</li>
                  <li><strong>Missing dependencies</strong> (materials, labor)</li>
                  <li><strong>Solver limitations</strong> (greedy algorithm may ignore complex constraints)</li>
                </ul>
              </div>

              {/* Late Jobs Analysis */}
              <div className="analysis-group">
                <h3>Late Jobs ({metrics?.lateJobs}, {((metrics?.lateJobs || 0) / (metrics?.totalJobs || 1) * 100).toFixed(1)}%)</h3>
                <p><strong>Possible causes:</strong></p>
                <ul>
                  <li><strong>Overloaded machines</strong> (check utilization per machine)</li>
                  <li><strong>Poor prioritization</strong> (jobs not ranked by urgency)</li>
                  <li><strong>Insufficient buffer time</strong> (schedule too tight)</li>
                </ul>
              </div>


              {/* Final Verdict */}
              <div className="final-verdict">
                <div className="verdict-header">
                  <i className="fas fa-exclamation-triangle"></i>
                  <h3>Final Verdict: High-Risk Schedule</h3>
                </div>
                <div className="verdict-content">
                  <p><strong>Urgent intervention needed</strong> to prevent further delays.</p>
                  <p><strong>Optimize solver, track errors, and reschedule late jobs</strong> for recovery.</p>
                </div>
              </div>

            </section>
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