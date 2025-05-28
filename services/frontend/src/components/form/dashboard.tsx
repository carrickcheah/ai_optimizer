import React from 'react';
import { Link } from 'react-router-dom';
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
      title: 'Manpower Allocation', 
      iconClass: 'fas fa-users-cog', 
      description: 'Assign personnel to production tasks based on skills, availability, and workload balancing.',
      linkTo: '/manpower',
      linkText: 'Manage Personnel'
    },
    { 
      title: 'Maintenance', 
      iconClass: 'fas fa-tools', 
      description: 'Schedule and track preventive and corrective maintenance activities for production equipment.',
      linkTo: '/maintenance',
      linkText: 'Manage Maintenance'
    },
    { 
      title: 'AI Report', 
      iconClass: 'fas fa-brain', 
      description: 'Generate AI-powered insights and reporting on production efficiency, bottlenecks, and optimization opportunities.',
      linkTo: '/reports',
      linkText: 'View Reports'
    },
    { 
      title: 'Settings', 
      iconClass: 'fas fa-cogs', 
      description: 'Configure system preferences, user access, notification rules, and integration settings.',
      linkTo: '/settings',
      linkText: 'Manage Settings'
    },
  ];

  return (
    <div className="dashboard-page-container">
      <div className="dashboard-main-content">
        <div className="dashboard-section-description">
          <div className="dashboard-header-container">
            <Link to="/input" className="dashboard-back-button">
              <i className="fas fa-arrow-left"></i>Back to Job Input
            </Link>
          </div>
          <h1 className="dashboard-title">AI Optimizer</h1>
          <p>Welcome to the AI Optimizer dashboard. Navigate through different modules to optimize your production planning, resource allocation, and efficiency analysis.</p>
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
