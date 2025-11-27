import React from 'react';
import './settings.css';

const Settings: React.FC = () => {
  return (
    <div className="settings-container">
      <div className="settings-header">
        <button
          className="back-button"
          onClick={() => window.location.href = '/'}
        >
          <i className="fas fa-home"></i> Home
        </button>
        <h1 className="settings-title">Settings</h1>
      </div>

      <div className="settings-content">
        <div className="settings-section">
          <h2>Application Settings</h2>
          <p className="settings-placeholder">Settings configuration coming soon.</p>
        </div>
      </div>
    </div>
  );
};

export default Settings;
