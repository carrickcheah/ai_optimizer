import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { API_BASE_URL } from '../config';

// Interface definitions
interface TaskData {
  Task: string;
  Start: string;
  Finish: string;
  Resource: string;
  PriorityInteger?: number;
  PriorityLabel?: string;
  Color?: string;
  Description?: string;
  JobFamily?: string;
  ProcessNumber?: number;
  BufferStatusLabel?: string;
}

interface ScheduleOverview {
  total_jobs: number;
  date_range: string;
  total_duration: string;
  records_displayed: number;
  buffer_status_counts: {
    Late: number;
    Critical: number;
    Warning: number;
    Caution: number;
    OK: number;
    Unknown: number;
  };
  config_used: {
    solver_type: string;
    max_jobs_limit: number;
    planning_horizon_days: number;
  };
}

interface DetailedScheduleRow {
  op_id: string;
  job_id: string;
  plan_date?: string;
  lcd_date_str?: string;
  LCD_DATE?: string;
  lcd_date?: string;
  due_date?: string;
  target_date?: string;
  job?: string;
  process_code?: string;
  job_dependency?: string;
  rsc_location?: string;
  rsc_code?: string;
  MachineName_v?: string;
  number_operator?: number;
  job_quantity?: number;
  expect_output_per_hour?: number;
  priority?: number;
  hours_need?: number;
  setting_hours?: number;
  break_hours?: number;
  no_prod?: number;
  [key: string]: any;
}

interface CachedData {
  ganttPriorityView: TaskData[];
  ganttResourceView: TaskData[];
  scheduleOverview: ScheduleOverview | null;
  detailedSchedule: DetailedScheduleRow[];
  lastRefresh: Date;
  isLoading: boolean;
  error: string | null;
}

interface DataCacheContextType {
  data: CachedData;
  refreshData: () => Promise<void>;
  loadDataIfNeeded: () => Promise<void>;
  clearError: () => void;
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
  // Initialize data from localStorage if available
  const getInitialData = (): CachedData => {
    try {
      const savedData = localStorage.getItem('scheduleDataCache');
      if (savedData) {
        const parsed = JSON.parse(savedData);
        // Convert lastRefresh back to Date object
        if (parsed.lastRefresh) {
          parsed.lastRefresh = new Date(parsed.lastRefresh);
        }
        console.log('[DataCache] Restored data from localStorage:', {
          ganttPriorityView: parsed.ganttPriorityView?.length || 0,
          ganttResourceView: parsed.ganttResourceView?.length || 0,
          detailedSchedule: parsed.detailedSchedule?.length || 0,
          lastRefresh: parsed.lastRefresh,
        });
        return parsed;
      }
    } catch (error) {
      console.warn('[DataCache] Failed to restore data from localStorage:', error);
    }
    
    return {
      ganttPriorityView: [],
      ganttResourceView: [],
      scheduleOverview: null,
      detailedSchedule: [],
      lastRefresh: new Date(),
      isLoading: false,
      error: null,
    };
  };

  const [data, setData] = useState<CachedData>(getInitialData);

  const [hasInitiallyLoaded, setHasInitiallyLoaded] = useState(() => {
    try {
      const savedData = localStorage.getItem('scheduleDataCache');
      return savedData ? JSON.parse(savedData).ganttPriorityView?.length > 0 : false;
    } catch {
      return false;
    }
  });

  const solver = 'cpsat'; // Always use CP-SAT solver

  // Save data to localStorage
  const saveDataToLocalStorage = (dataToSave: CachedData) => {
    try {
      localStorage.setItem('scheduleDataCache', JSON.stringify(dataToSave));
      console.log('[DataCache] Saved data to localStorage');
    } catch (error) {
      console.warn('[DataCache] Failed to save data to localStorage:', error);
    }
  };

  // Calculate time until next 6am Singapore time
  const getTimeUntilNext6AMSingapore = () => {
    const now = new Date();
    
    // Get current time in Singapore timezone
    const nowSingapore = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Singapore"}));
    
    // Create next 6 AM Singapore time
    const next6AMSingapore = new Date(nowSingapore);
    next6AMSingapore.setHours(6, 0, 0, 0);
    
    // If it's already past 6am Singapore time today, set to 6am tomorrow Singapore time
    if (nowSingapore >= next6AMSingapore) {
      next6AMSingapore.setDate(next6AMSingapore.getDate() + 1);
    }
    
    // Convert back to local time for setTimeout calculation
    const next6AMLocal = new Date(next6AMSingapore.toLocaleString("en-US", {timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone}));
    
    return next6AMLocal.getTime() - now.getTime();
  };

  const refreshData = async () => {
    console.log('[DataCache] Starting data refresh...');
    
    setData(prev => ({ 
      ...prev, 
      isLoading: true, 
      error: null 
    }));

    try {
      // Fetch all data in parallel
      const [
        ganttPriorityResponse,
        ganttResourceResponse,
        scheduleOverviewResponse,
        detailedScheduleResponse
      ] = await Promise.all([
        fetch(`${API_BASE_URL}/reports/gantt/priority-view?solver=${solver}`),
        fetch(`${API_BASE_URL}/reports/gantt/resource-view?solver=${solver}`),
        fetch(`${API_BASE_URL}/reports/schedule-overview?solver=${solver}`),
        fetch(`${API_BASE_URL}/reports/detailed-schedule?solver=${solver}`)
      ]);

      // Check if all responses are ok
      if (!ganttPriorityResponse.ok) {
        throw new Error(`Gantt Priority View failed: ${ganttPriorityResponse.status}`);
      }
      if (!ganttResourceResponse.ok) {
        throw new Error(`Gantt Resource View failed: ${ganttResourceResponse.status}`);
      }
      if (!scheduleOverviewResponse.ok) {
        throw new Error(`Schedule Overview failed: ${scheduleOverviewResponse.status}`);
      }
      if (!detailedScheduleResponse.ok) {
        throw new Error(`Detailed Schedule failed: ${detailedScheduleResponse.status}`);
      }

      // Parse all responses
      const [
        ganttPriorityData,
        ganttResourceData,
        scheduleOverviewData,
        detailedScheduleData
      ] = await Promise.all([
        ganttPriorityResponse.json(),
        ganttResourceResponse.json(),
        scheduleOverviewResponse.json(),
        detailedScheduleResponse.json()
      ]);

      console.log('[DataCache] Data refresh completed successfully');
      console.log('[DataCache] Gantt Priority tasks:', ganttPriorityData.length);
      console.log('[DataCache] Gantt Resource tasks:', ganttResourceData.length);
      console.log('[DataCache] Detailed schedule rows:', detailedScheduleData.length);

      setData(prev => ({
        ...prev,
        ganttPriorityView: ganttPriorityData,
        ganttResourceView: ganttResourceData,
        scheduleOverview: scheduleOverviewData,
        detailedSchedule: detailedScheduleData,
        lastRefresh: new Date(),
        isLoading: false,
        error: null,
      }));

      setHasInitiallyLoaded(true);

    } catch (error) {
      console.error('[DataCache] Error refreshing data:', error);
      setData(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      }));
      setHasInitiallyLoaded(true);
    }
  };

  const clearError = () => {
    setData(prev => ({ ...prev, error: null }));
  };

  // One-time initial load when first needed
  const loadDataIfNeeded = async () => {
    if (!hasInitiallyLoaded && !data.isLoading && data.ganttPriorityView.length === 0) {
      console.log('[DataCache] Performing one-time initial data load');
      await refreshData();
    }
  };

  useEffect(() => {
    // Only set up daily 6am Singapore time refresh - NO AUTOMATIC INITIAL FETCH
    const timeUntil6AM = getTimeUntilNext6AMSingapore();
    console.log('[DataCache] Next 6AM Singapore refresh in:', Math.round(timeUntil6AM / 1000 / 60), 'minutes');
    console.log('[DataCache] Data will be loaded when first needed');
    
    const dailyRefreshTimeout = setTimeout(() => {
      console.log('[DataCache] Daily 6AM Singapore time auto-refresh triggered');
      refreshData();
      
      // Schedule next day's 6am refresh
      const nextDayTimeout = setTimeout(() => {
        refreshData();
      }, 24 * 60 * 60 * 1000); // 24 hours
      
      return () => clearTimeout(nextDayTimeout);
    }, timeUntil6AM);

    // Cleanup timeout on component unmount
    return () => clearTimeout(dailyRefreshTimeout);
  }, []);

  const contextValue: DataCacheContextType = {
    data,
    refreshData,
    loadDataIfNeeded,
    clearError,
  };

  return (
    <DataCacheContext.Provider value={contextValue}>
      {children}
    </DataCacheContext.Provider>
  );
};