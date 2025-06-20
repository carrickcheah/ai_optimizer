import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface CachedData {
  ganttPriorityView: any[];
  ganttResourceView: any[];
  detailedSchedule: any[];
  scheduleOverview: any;
  systemLogs: any[];
  isLoading: boolean;
  error: string | null;
  lastRefresh: Date;
}

interface DataCacheContextType {
  data: CachedData;
  refreshData: () => Promise<void>;
  clearError: () => void;
  clearCache: () => void;
}

const DataCacheContext = createContext<DataCacheContextType | undefined>(undefined);

export const useDataCache = () => {
  const context = useContext(DataCacheContext);
  if (context === undefined) {
    throw new Error('useDataCache must be used within a DataCacheProvider');
  }
  return context;
};

interface DataCacheProviderProps {
  children: ReactNode;
}

export const DataCacheProvider: React.FC<DataCacheProviderProps> = ({ children }) => {
  const [data, setData] = useState<CachedData>({
    ganttPriorityView: [],
    ganttResourceView: [],
    detailedSchedule: [],
    scheduleOverview: null,
    systemLogs: [],
    isLoading: false,
    error: null,
    lastRefresh: new Date(),
  });

  // Check if we have cached data in localStorage that's still valid
  const [hasValidCache, setHasValidCache] = useState(() => {
    try {
      const savedData = localStorage.getItem('aiOptimizerCache');
      return savedData ? JSON.parse(savedData).ganttPriorityView?.length > 0 : false;
    } catch {
      return false;
    }
  });

  const solver = 'greedy'; // Use greedy solver (CP-SAT disabled)

  // Save data to localStorage
  const saveDataToLocalStorage = (dataToSave: CachedData) => {
    try {
      localStorage.setItem('aiOptimizerCache', JSON.stringify(dataToSave));
    } catch (error) {
      console.warn('Failed to save data to localStorage:', error);
    }
  };

  // Load data from localStorage
  const loadDataFromLocalStorage = (): CachedData | null => {
    try {
      const savedData = localStorage.getItem('aiOptimizerCache');
      if (savedData) {
        const parsedData = JSON.parse(savedData);
        return {
          ...parsedData,
          lastRefresh: new Date(parsedData.lastRefresh),
        };
      }
    } catch (error) {
      console.warn('Failed to load data from localStorage:', error);
    }
    return null;
  };

  const refreshData = async () => {
    console.log('🔄 DataCacheContext: Starting refreshData...');
    setData(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/api$/, '');
      console.log('📡 DataCacheContext: Using API_BASE_URL:', API_BASE_URL);
      console.log('🔧 DataCacheContext: Using solver:', solver);
      
      // Fetch all data concurrently
      console.log('🚀 DataCacheContext: Starting concurrent API calls...');
      const [ganttPriorityResponse, ganttResourceResponse, detailedScheduleResponse, scheduleOverviewResponse, logsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/reports/gantt/priority-view?solver=${solver}&force_refresh=true`),
        fetch(`${API_BASE_URL}/api/reports/gantt/resource-view?solver=${solver}&force_refresh=true`),
        fetch(`${API_BASE_URL}/api/reports/detailed-schedule?solver=${solver}&force_refresh=true`),
        fetch(`${API_BASE_URL}/api/reports/schedule-overview?solver=${solver}&force_refresh=true`),
        fetch(`${API_BASE_URL}/api/logs/recent?lines=500`)
      ]);

      console.log('📊 DataCacheContext: API responses:', {
        ganttPriority: ganttPriorityResponse.status,
        ganttResource: ganttResourceResponse.status,
        detailedSchedule: detailedScheduleResponse.status,
        scheduleOverview: scheduleOverviewResponse.status,
        logs: logsResponse.status
      });

      if (!ganttPriorityResponse.ok || !ganttResourceResponse.ok || !detailedScheduleResponse.ok || !scheduleOverviewResponse.ok || !logsResponse.ok) {
        const errors = [];
        if (!ganttPriorityResponse.ok) errors.push(`ganttPriority: ${ganttPriorityResponse.status}`);
        if (!ganttResourceResponse.ok) errors.push(`ganttResource: ${ganttResourceResponse.status}`);
        if (!detailedScheduleResponse.ok) errors.push(`detailedSchedule: ${detailedScheduleResponse.status}`);
        if (!scheduleOverviewResponse.ok) errors.push(`scheduleOverview: ${scheduleOverviewResponse.status}`);
        if (!logsResponse.ok) errors.push(`logs: ${logsResponse.status}`);
        throw new Error(`API requests failed: ${errors.join(', ')}`);
      }

      console.log('🔄 DataCacheContext: Parsing JSON responses...');
      const [ganttPriorityData, ganttResourceData, detailedScheduleData, scheduleOverviewData, logsData] = await Promise.all([
        ganttPriorityResponse.json(),
        ganttResourceResponse.json(),
        detailedScheduleResponse.json(),
        scheduleOverviewResponse.json(),
        logsResponse.json()
      ]);

      console.log('📈 DataCacheContext: Data sizes:', {
        ganttPriority: ganttPriorityData.length,
        ganttResource: ganttResourceData.length,
        detailedSchedule: detailedScheduleData.length,
        scheduleOverview: scheduleOverviewData ? 'present' : 'missing',
        logs: logsData.logs ? logsData.logs.length : 0
      });

      const newData: CachedData = {
        ganttPriorityView: ganttPriorityData,
        ganttResourceView: ganttResourceData,
        detailedSchedule: detailedScheduleData,
        scheduleOverview: scheduleOverviewData,
        systemLogs: logsData.logs || [],
        isLoading: false,
        error: null,
        lastRefresh: new Date(),
      };

      setData(newData);
      saveDataToLocalStorage(newData);
      setHasValidCache(true);
      
      console.log('✅ DataCacheContext: Successfully refreshed all data!');
      
    } catch (error) {
      console.error('❌ DataCacheContext: Error during refresh:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch data';
      setData(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
    }
  };

  const clearError = () => {
    setData(prev => ({ ...prev, error: null }));
  };

  const clearCache = () => {
    console.log('🗑️ DataCacheContext: Clearing localStorage cache...');
    try {
      localStorage.removeItem('aiOptimizerCache');
      setData({
        ganttPriorityView: [],
        ganttResourceView: [],
        detailedSchedule: [],
        scheduleOverview: null,
        isLoading: false,
        error: null,
        lastRefresh: new Date(),
      });
      setHasValidCache(false);
      console.log('✅ DataCacheContext: Cache cleared successfully');
    } catch (error) {
      console.warn('Failed to clear cache:', error);
    }
  };

  // Load cached data on mount
  useEffect(() => {
    const cachedData = loadDataFromLocalStorage();
    if (cachedData && cachedData.ganttPriorityView.length > 0) {
      setData(cachedData);
      setHasValidCache(true);
    }
  }, []);


  // Provide the context value
  const contextValue: DataCacheContextType = {
    data,
    refreshData,
    clearError,
    clearCache,
  };

  return (
    <DataCacheContext.Provider value={contextValue}>
      {children}
    </DataCacheContext.Provider>
  );
};