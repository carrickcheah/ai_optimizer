import React, { useState } from 'react';
import { useAuth } from '@/auth';
import { Button } from '@/components/ui/button';
import { UserProfile } from '@/auth/UserProfile';
import './header.css';

interface HeaderProps {
  title: string;
}

const Header: React.FC<HeaderProps> = ({ title }) => {
  const { user, signOut } = useAuth();
  const [showProfile, setShowProfile] = useState(false);

  const navItemClasses = (pageTitle: string): string => {
    return `nav-item ${title === pageTitle ? 'active' : ''}`;
  };

  const handleSignOut = async () => {
    await signOut();
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
      
      {/* User Profile Section */}
      <div className="user-section flex items-center space-x-4 mr-4">
        <span className="text-sm text-white font-medium">
          Welcome, {user?.email}
        </span>
        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowProfile(!showProfile)}
            className="text-xs"
          >
            Profile
          </Button>
          {showProfile && (
            <div className="absolute right-0 top-full mt-2 z-50">
              <UserProfile />
            </div>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleSignOut}
          className="text-xs"
        >
          Sign Out
        </Button>
      </div>
    </div>
  );
};

export default Header;

