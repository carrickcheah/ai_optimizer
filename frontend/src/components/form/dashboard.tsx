import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useDataCache } from '../../contexts/DataCacheContext';
import './dashboard.css';

// Make sure Font Awesome is linked in your project's main HTML file or installed via npm/yarn
// Also ensure the Poppins font is loaded via Google Fonts in your main HTML or global CSS

interface DashboardCardProps {
  title: string;
  iconClass: string;
  description: string;
  linkTo: string;
  linkText: string;
}

const DashboardCard: React.FC<DashboardCardProps> = ({ 
  title, 
  iconClass, 
  description,
  linkTo,
  linkText 
}) => {
  return (
    <div className="dashboard-menu-card">
      <div className="dashboard-card-body">
        <div className="dashboard-card-icon">
          <i className={iconClass}></i>
        </div>
        <h3 className="dashboard-card-title">{title}</h3>
        <p className="dashboard-card-text">{description}</p>
        <Link to={linkTo} className="dashboard-card-btn">{linkText}</Link>
      </div>
    </div>
  );
};

const Dashboard: React.FC = () => {
  const { refreshData, clearError, clearCache } = useDataCache();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshLogs, setRefreshLogs] = useState<string[]>([]);

  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setRefreshLogs(prev => [...prev, `[${timestamp}] ${message}`]);
  };

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    setRefreshLogs([]);
    addLog('🔄 Starting data refresh...');
    clearError();
    
    try {
      // Clear cache first
      addLog('🗑️ Clearing cache...');
      clearCache();
      await new Promise(resolve => setTimeout(resolve, 300));
      
      // Fetching schedule data with animated dots
      addLog('📡 Fetching schedule data...');

      
      // Loading Gantt chart data with animated dots
      addLog('📊 Loading Gantt chart data...');
      await new Promise(resolve => setTimeout(resolve, 500));
      addLog('🏭 The App is scheduling now...');
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Retrieving resource allocation
      addLog('🏭 The jobs will finish scheduling in 60 seconds...');
      await refreshData();
      
      // Clear processing logs and show final success messages
      setRefreshLogs([]);
      addLog('✅ DONE!');
      addLog('✅ All data refreshed successfully!');
      addLog('✅ Now you can view the schedule!');
      
      // Don't clear the final success messages - they stay visible
    } catch (error) {
      console.error('Dashboard refresh error:', error);
      addLog(`❌ Error occurred during refresh: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsRefreshing(false);
    }
  };

  const dashboardItems: DashboardCardProps[] = [
    { 
      title: 'Data', 
      iconClass: 'fas fa-database', 
      description: 'Manage and visualize production data, including job details, resource allocations, and historical metrics.',
      linkTo: '/data',
      linkText: 'Manage Data'
    },
    { 
      title: 'Schedule Table', 
      iconClass: 'fas fa-calendar-alt', 
      description: 'View and interact with comprehensive production schedules and timeline visualizations.',
      linkTo: '/schedule-table',
      linkText: 'View Schedule'
    },
    { 
      title: 'Jobs Allocation', 
      iconClass: 'fas fa-tasks', 
      description: 'Optimize job assignments across production facilities using AI-driven allocation algorithms.',
      linkTo: '/gantt-chart',
      linkText: 'View Jobs Allocation'
    },
    { 
      title: 'Machine Allocation', 
      iconClass: 'fas fa-robot', 
      description: 'Allocate machines and equipment to jobs based on availability, capability, and efficiency.',
      linkTo: '/resource-chart',
      linkText: 'View Machine Allocation'
    },
    { 
      title: 'AI Report', 
      iconClass: 'fas fa-brain', 
      description: 'Generate AI-powered insights and reporting on production efficiency, bottlenecks, and optimization opportunities.',
      linkTo: '/reports',
      linkText: 'View Reports'
    },
  ];

  return (
    <div className="dashboard-page-container">
      <div className="dashboard-main-content">
        <div className="dashboard-section-description">
          <div className="d-flex align-items-center justify-content-between mb-3">
            <h1 className="dashboard-title mb-0">AI Optimizer</h1>
            <button 
              className="btn btn-primary" 
              onClick={handleRefreshAll}
              disabled={isRefreshing}
            >
              <i className="fas fa-sync-alt"></i> {isRefreshing ? 'Refreshing All Data...' : 'Refresh All Data'}
            </button>
          </div>

          
          {/* Progress Log Display */}
          {refreshLogs.length > 0 && (
            <div className="refresh-log-container">
              <h4>Data Refresh Progress</h4>
              <div className="refresh-log-content">
                {refreshLogs.map((log, index) => (
                  <div key={index} className="refresh-log-item">
                    {log}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        
        <div className="dashboard-cards-container">
          {dashboardItems.map((item, index) => (
            <DashboardCard 
              key={index} 
              title={item.title} 
              iconClass={item.iconClass}
              description={item.description}
              linkTo={item.linkTo}
              linkText={item.linkText}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
