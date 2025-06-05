import React from 'react';
import './header.css';

interface HeaderProps {
  title: string;
}

const Header: React.FC<HeaderProps> = ({ title }) => {
  const navItemClasses = (pageTitle: string): string => {
    return `nav-item ${title === pageTitle ? 'active' : ''}`;
  };

  return (
    <div className="nex-header">
      <div className="main-nav">
        <a href="/page/dashboard" className={navItemClasses('Dashboard')}>
          <i className="fas fa-tachometer-alt"></i> Dashboard
        </a>
        <a href="/page/sales" className={navItemClasses('Sales')}>
          <i className="fas fa-chart-line"></i> Sales
        </a>
        <a href="/page/purchasing" className={navItemClasses('Purchasing')}>
          <i className="fas fa-shopping-cart"></i> Purchasing
        </a>
        <a href="/page/warehouse" className={navItemClasses('Warehouse')}>
          <i className="fas fa-warehouse"></i> Warehouse
        </a>
        <a href="/page/manufacturing" className={navItemClasses('Manufacturing')}>
          <i className="fas fa-industry"></i> Manufacturing
        </a>
        <a href="/page/engineering" className={navItemClasses('Engineering')}>
          <i className="fas fa-cogs"></i> Engineering
        </a>
        <a href="/page/administration" className={navItemClasses('Administration')}>
          <i className="fas fa-users-cog"></i> Administration
        </a>
        <a href="/page/aichat" className={navItemClasses('AI Chat')}>
          <i className="fas fa-comment-dots"></i> AI Chat
        </a>
        <a href="/page/ai_optimizer" className={navItemClasses('AI Optimizer')}>
          <i className="fas fa-cog"></i> AI Optimizer
        </a>
      </div>
    </div>
  );
};

export default Header;

