import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';

// Type definitions for API responses
export interface GanttTask {
  Task: string;
  Resource: string;
  Start: string;
  Finish: string;
  job_id?: string;
  machine?: string;
  start_time?: string;
  end_time?: string;
  processing_time?: number;
  setup_time?: number;
  buffer_hours?: number;
  priority?: number;
  lcd_date?: string;
  status?: string;
}

export interface DetailedScheduleItem {
  job_id: string;
  job?: string;
  machine?: string;
  machine_name?: string;
  start_time?: string;
  end_time?: string;
  scheduled_start_time_str?: string;
  scheduled_end_time_str?: string;
  scheduled_start_epoch?: number;
  scheduled_end_epoch?: number;
  processing_time?: number;
  setup_time?: number;
  buffer_hours?: number;
  actual_buffer_hours?: number;
  priority?: number;
  lcd_date?: string;
  lcd_date_str?: string;
  lcd_date_epoch?: number;
  status?: string;
  buffer_status?: string;
  process_code?: string;
  plan_date?: string;
  start_date_input_str?: string;
  start_date_input_epoch?: number;
  job_dependency?: string;
  rsc_location?: string;
  MachineName_v?: string;
  number_operator?: number;
  job_quantity?: number;
  expect_output_per_hour?: number;
  hours_need?: number;
  setting_hours?: number;
  break_hours?: number;
  no_prod?: number;
  accumulated_daily_output?: number;
  balance_quantity?: number;
  bal_hr?: number;
}

export interface ScheduleOverview {
  total_jobs?: number;
  scheduled_jobs?: number;
  unscheduled_jobs?: number;
  total_machines?: number;
  utilization?: Record<string, number>;
  summary?: Record<string, unknown>;
}

export interface LogEntry {
  timestamp: string;
  module: string;
  level: string;
  message: string;
}

interface CachedData {
  ganttPriorityView: GanttTask[];
  ganttResourceView: GanttTask[];
  detailedSchedule: DetailedScheduleItem[];
  scheduleOverview: ScheduleOverview | null;
  systemLogs: LogEntry[];
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
  // Track mounted state to prevent state updates on unmounted component
  const mountedRef = useRef(true);

  // Initialize state - try to load from localStorage first
  const [data, setData] = useState<CachedData>(() => {
    console.log('DataCacheContext: Initializing state...');
    try {
      const savedData = localStorage.getItem('aiOptimizerCache');
      console.log('DataCacheContext: localStorage data exists:', !!savedData);
      if (savedData) {
        const parsedData = JSON.parse(savedData);
        console.log('DataCacheContext: Parsed data has', parsedData.detailedSchedule?.length || 0, 'jobs');
        if (parsedData.detailedSchedule?.length > 0) {
          console.log('DataCacheContext: Loading from localStorage:', {
            detailedSchedule: parsedData.detailedSchedule?.length || 0,
            ganttPriorityView: parsedData.ganttPriorityView?.length || 0
          });
          return {
            ...parsedData,
            lastRefresh: new Date(parsedData.lastRefresh),
            isLoading: false,
            error: null,
          };
        }
      }
    } catch (error) {
      console.warn('DataCacheContext: Failed to load from localStorage:', error);
    }
    console.log('DataCacheContext: Starting with empty state');
    return {
      ganttPriorityView: [],
      ganttResourceView: [],
      detailedSchedule: [],
      scheduleOverview: null,
      systemLogs: [],
      isLoading: false,
      error: null,
      lastRefresh: new Date(),
    };
  });

  const solver = 'greedy'; // Use greedy solver (CP-SAT disabled)

  // Save data to localStorage (excluding logs to reduce size)
  const saveDataToLocalStorage = (dataToSave: CachedData) => {
    console.log('DataCacheContext: saveDataToLocalStorage called');
    try {
      // Exclude systemLogs to reduce localStorage size (they can exceed 5MB limit)
      const dataToStore = {
        ...dataToSave,
        systemLogs: [], // Don't persist logs
        lastRefresh: dataToSave.lastRefresh.toISOString(), // Serialize Date as string
      };
      const jsonString = JSON.stringify(dataToStore);

      // Check size before saving (localStorage limit is typically 5MB)
      const sizeInMB = new Blob([jsonString]).size / (1024 * 1024);
      console.log(`DataCacheContext: Data size is ${sizeInMB.toFixed(2)}MB`);

      if (sizeInMB > 4.5) {
        console.warn(`DataCacheContext: Data too large for localStorage (${sizeInMB.toFixed(2)}MB), skipping save`);
        return;
      }

      localStorage.setItem('aiOptimizerCache', jsonString);
      console.log(`DataCacheContext: Saved to localStorage (${sizeInMB.toFixed(2)}MB)`);
    } catch (error) {
      console.error('DataCacheContext: Failed to save to localStorage:', error);
    }
  };


  const refreshData = async (retryCount = 0) => {
    const MAX_RETRIES = 2;
    if (import.meta.env.DEV) console.log('DataCacheContext: Starting refreshData...');
    setData(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/api$/, '');
      if (import.meta.env.DEV) {
        console.log('DataCacheContext: Using API_BASE_URL:', API_BASE_URL);
        console.log('DataCacheContext: Using solver:', solver);
      }

      // Fetch all data concurrently
      const [ganttPriorityResponse, ganttResourceResponse, detailedScheduleResponse, scheduleOverviewResponse, logsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/reports/gantt/priority-view?solver=${solver}&force_refresh=true`),
        fetch(`${API_BASE_URL}/api/reports/gantt/resource-view?solver=${solver}&force_refresh=true`),
        fetch(`${API_BASE_URL}/api/reports/detailed-schedule?solver=${solver}&force_refresh=true`),
        fetch(`${API_BASE_URL}/api/reports/schedule-overview?solver=${solver}&force_refresh=true`),
        fetch(`${API_BASE_URL}/api/logs/recent?lines=500`)
      ]);

      if (import.meta.env.DEV) {
        console.log('DataCacheContext: API responses:', {
          ganttPriority: ganttPriorityResponse.status,
          ganttResource: ganttResourceResponse.status,
          detailedSchedule: detailedScheduleResponse.status,
          scheduleOverview: scheduleOverviewResponse.status,
          logs: logsResponse.status
        });
      }

      if (!ganttPriorityResponse.ok || !ganttResourceResponse.ok || !detailedScheduleResponse.ok || !scheduleOverviewResponse.ok || !logsResponse.ok) {
        const errors = [];
        if (!ganttPriorityResponse.ok) errors.push(`ganttPriority: ${ganttPriorityResponse.status}`);
        if (!ganttResourceResponse.ok) errors.push(`ganttResource: ${ganttResourceResponse.status}`);
        if (!detailedScheduleResponse.ok) errors.push(`detailedSchedule: ${detailedScheduleResponse.status}`);
        if (!scheduleOverviewResponse.ok) errors.push(`scheduleOverview: ${scheduleOverviewResponse.status}`);
        if (!logsResponse.ok) errors.push(`logs: ${logsResponse.status}`);
        throw new Error(`API requests failed: ${errors.join(', ')}`);
      }

      const [ganttPriorityData, ganttResourceData, detailedScheduleData, scheduleOverviewData, logsData] = await Promise.all([
        ganttPriorityResponse.json(),
        ganttResourceResponse.json(),
        detailedScheduleResponse.json(),
        scheduleOverviewResponse.json(),
        logsResponse.json()
      ]);

      if (import.meta.env.DEV) {
        console.log('DataCacheContext: Data loaded:', {
          ganttPriority: ganttPriorityData.length,
          ganttResource: ganttResourceData.length,
          detailedSchedule: detailedScheduleData.length,
          logs: logsData.logs ? logsData.logs.length : 0
        });
      }

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

      // Always save to localStorage (safe even if component unmounted)
      saveDataToLocalStorage(newData);

      // Only update React state if component is still mounted
      if (mountedRef.current) {
        setData(newData);
        console.log('DataCacheContext: State updated successfully');
      } else {
        console.log('DataCacheContext: Component unmounted during fetch, data saved to localStorage only');
      }

      console.log('DataCacheContext: Successfully refreshed all data');

    } catch (error) {
      console.error('DataCacheContext: Error during refresh:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch data';

      // Retry logic for transient failures
      if (retryCount < MAX_RETRIES) {
        console.warn(`DataCacheContext: Retrying request (attempt ${retryCount + 1}/${MAX_RETRIES})...`);
        setTimeout(() => {
          if (mountedRef.current) {
            refreshData(retryCount + 1);
          }
        }, 1000 * (retryCount + 1)); // Exponential backoff
        return;
      }

      // Only update state if component is still mounted
      if (mountedRef.current) {
        setData(prev => ({
          ...prev,
          isLoading: false,
          error: errorMessage,
        }));
      }
    }
  };

  const clearError = () => {
    setData(prev => ({ ...prev, error: null }));
  };

  const clearCache = async () => {
    console.log('DataCacheContext: Clearing localStorage and backend caches...');
    try {
      // Clear frontend localStorage cache
      localStorage.removeItem('aiOptimizerCache');
      setData({
        ganttPriorityView: [],
        ganttResourceView: [],
        detailedSchedule: [],
        scheduleOverview: null,
        systemLogs: [],
        isLoading: false,
        error: null,
        lastRefresh: new Date(),
      });
      console.log('DataCacheContext: Frontend cache cleared');

      // Clear backend caches
      try {
        const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/api$/, '');
        const response = await fetch(`${API_BASE_URL}/api/reports/clear-cache`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const result = await response.json();
          console.log('DataCacheContext: Backend caches cleared:', result.message);
        } else {
          console.warn('DataCacheContext: Backend cache clearing failed:', response.statusText);
        }
      } catch (backendError) {
        console.warn('DataCacheContext: Could not clear backend caches:', backendError);
        // Don't throw - frontend cache clearing still succeeded
      }

      console.log('DataCacheContext: All caches cleared successfully');
    } catch (error) {
      console.warn('Failed to clear cache:', error);
      throw error; // Re-throw so calling code knows it failed
    }
  };

  // Track mount state - reset to true on mount, false on unmount
  // This handles React Strict Mode double-mounting correctly
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
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