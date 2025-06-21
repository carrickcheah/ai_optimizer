import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider, ProtectedRoute } from './auth';
import { DataCacheProvider } from './contexts/DataCacheContext';
import InputForm from './components/form/input';
import Header from './components/header';
import Dashboard from './components/form/dashboard';
import TableData from './components/form/table_data';
import JobView from './components/form/view';
import DetailedScheduleTable from './components/DetailedScheduleTable';
import GanttChartDisplay from './components/GanttChartDisplay';
import ResourceChart from './components/resource_chart';
import AIReport from './components/form/ai_report';

function App() {
  return (
    <AuthProvider>
      <DataCacheProvider>
        <Router>
          <ProtectedRoute>
            <div className="app-container bg-gray-100 min-h-screen">
              <Header title="AI Optimizer" />
              <main className="main-content p-4">
                <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/page/ai_optimizer" element={<Dashboard />} />
              <Route path="/input" element={<InputForm />} />
              <Route path="/data" element={<TableData />} />
              <Route path="/table_data" element={<TableData />} />
              <Route path="/job/view/:id" element={<JobView />} />
              <Route path="/job/edit/:id" element={<InputForm />} />
              
              {/* Schedule visualizations */}
              <Route path="/schedule-table" element={<DetailedScheduleTable />} />
              
              {/* Jobs Allocation - Priority View Gantt Chart */}
              <Route path="/gantt-chart" element={
                <div>
                  <h2 className="text-xl font-semibold mb-4">Jobs Allocation</h2>
                  <GanttChartDisplay title="Jobs Allocation (Priority View)" />
                </div>
              } />
              
              {/* Machine Allocation - Resource View Gantt Chart */}
              <Route path="/resource-chart" element={
                <div>
                  <h2 className="text-xl font-semibold mb-4">Machine Allocation</h2>
                  <ResourceChart title="Machine Allocation (Resource View)" />
                </div>
              } />
              
              {/* AI Report */}
              <Route path="/reports" element={<AIReport />} />
                </Routes>
              </main>
            </div>
          </ProtectedRoute>
        </Router>
      </DataCacheProvider>
    </AuthProvider>
  );
}

export default App;
