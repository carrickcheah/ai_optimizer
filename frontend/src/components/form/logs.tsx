import React, { useState, useMemo } from 'react';
import { useDataCache } from '../../contexts/DataCacheContext';
import './logs.css';

interface LogEntry {
  timestamp: string;
  module: string;
  level: string;
  message: string;
}

const Logs: React.FC = () => {
  const { data } = useDataCache();
  const [filter, setFilter] = useState('');
  const [levelFilter, setLevelFilter] = useState('ALL');
  
  // Filter logs based on search term and level
  const filteredLogs = useMemo(() => {
    if (!data.systemLogs || data.systemLogs.length === 0) {
      return [];
    }
    
    return data.systemLogs.filter((log: LogEntry) => {
      const matchesSearch = !filter || 
        log.message.toLowerCase().includes(filter.toLowerCase()) ||
        log.module.toLowerCase().includes(filter.toLowerCase());
      
      const matchesLevel = levelFilter === 'ALL' || log.level === levelFilter;
      
      return matchesSearch && matchesLevel;
    });
  }, [data.systemLogs, filter, levelFilter]);

  // Get log level badge class
  const getLevelBadgeClass = (level: string) => {
    switch (level) {
      case 'ERROR':
        return 'badge-error';
      case 'WARNING':
        return 'badge-warning';
      case 'INFO':
        return 'badge-info';
      case 'DEBUG':
        return 'badge-debug';
      default:
        return 'badge-default';
    }
  };

  // Format timestamp for display
  const formatTimestamp = (timestamp: string) => {
    if (!timestamp) return 'N/A';
    try {
      // Parse the timestamp format: 2025-06-20 23:22:35,984
      const [date, timeWithMs] = timestamp.split(' ');
      const [time] = timeWithMs.split(',');
      return `${date} ${time}`;
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="logs-container">
      <div className="logs-header">
        <button 
          className="back-button" 
          onClick={() => window.history.back()}
        >
          <i className="fas fa-arrow-left"></i> Back
        </button>
        <h1>System Logs</h1>
      </div>

      <div className="logs-content">
        <div className="logs-filters">
          <div className="filter-group">
            <label htmlFor="search-filter">Search:</label>
            <input
              id="search-filter"
              type="text"
              placeholder="Search logs..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="search-input"
            />
          </div>
          
          <div className="filter-group">
            <label htmlFor="level-filter">Level:</label>
            <select 
              id="level-filter"
              value={levelFilter} 
              onChange={(e) => setLevelFilter(e.target.value)}
              className="level-select"
            >
              <option value="ALL">All Levels</option>
              <option value="ERROR">Error</option>
              <option value="WARNING">Warning</option>
              <option value="INFO">Info</option>
              <option value="DEBUG">Debug</option>
            </select>
          </div>
          
          <div className="logs-info">
            Showing {filteredLogs.length} of {data.systemLogs?.length || 0} logs
          </div>
        </div>

        <div className="logs-table-container">
          {data.isLoading ? (
            <div className="logs-loading">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
              <p>Loading logs...</p>
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="logs-empty">
              <i className="fas fa-info-circle"></i>
              <p>No logs found. Click "Refresh All Data" on the dashboard to load logs.</p>
            </div>
          ) : (
            <table className="logs-table">
              <thead>
                <tr>
                  <th className="timestamp-col">Timestamp</th>
                  <th className="level-col">Level</th>
                  <th className="module-col">Module</th>
                  <th className="message-col">Message</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log: LogEntry, index: number) => (
                  <tr key={index} className={`log-row log-${log.level.toLowerCase()}`}>
                    <td className="timestamp-col">{formatTimestamp(log.timestamp)}</td>
                    <td className="level-col">
                      <span className={`log-level-badge ${getLevelBadgeClass(log.level)}`}>
                        {log.level}
                      </span>
                    </td>
                    <td className="module-col">{log.module}</td>
                    <td className="message-col">{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

export default Logs;