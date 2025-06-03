import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { API_BASE_URL } from '../config'; // Assuming your API base URL is configured here
import { PlotData } from 'plotly.js';
import './GanttChartDisplay.css'; // Import the CSS file

interface TaskData {
  Task: string;      // Typically the y-axis label for the task (e.g., UNIQUE_JOB_ID)
  Start: string;     // Start datetime string, e.g., "YYYY-MM-DD HH:MM:SS"
  Finish: string;    // End datetime string
  Resource: string;  // Machine or resource responsible
  PriorityInteger?: number;
  PriorityLabel?: string;
  Color?: string;       // Color for the task bar
  Description?: string; // HTML string for hover tooltip
  JobFamily?: string;
  ProcessNumber?: number;
  BufferStatusLabel?: string;
  // Add any other fields that come from the backend and might be useful
}

// Helper function to parse task string into job group and process number
const getTaskParts = (taskString: string): { jobGroup: string; processNum: number } => {
  const lastPIndex = taskString.lastIndexOf('-P');
  
  // If '-P' is not found, or it's not followed by a number, treat the whole string as the job group
  // and assign a default process number (e.g., 0 or a high number if unparsed should go last).
  // For "P1 first" (visually top), unparsable ones could be at the bottom of their group if processNum is high.
  // Or top if processNum is low (e.g. -1 or 0). Let's use 0 for now.
  if (lastPIndex === -1 || lastPIndex >= taskString.length - 2) {
    // console.warn(`[GanttChart] Task string "${taskString}" does not follow expected 'JOB-Pxx' format.`);
    return { jobGroup: taskString, processNum: 0 }; // Default if parsing fails
  }

  const jobGroup = taskString.substring(0, lastPIndex);
  const processNumStr = taskString.substring(lastPIndex + 2);
  const processNum = parseInt(processNumStr, 10);

  if (isNaN(processNum)) {
    // console.warn(`[GanttChart] Could not parse process number from "${processNumStr}" in task "${taskString}".`);
    return { jobGroup: jobGroup, processNum: 0 }; // Default if number parsing fails
  }
  
  return { jobGroup, processNum };
};

const GanttChartDisplay: React.FC = () => {
  const [tasks, setTasks] = useState<TaskData[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<string>('all');
  const [solver] = useState<string>('cpsat'); // Always use CP-SAT solver
  const [chartTitle, setChartTitle] = useState<string>('Production Planning System');
  const [overview, setOverview] = useState<{
    total_jobs: number;
    buffer_status_counts: {
      Late: number;
      Warning: number;
      Caution: number;
      OK: number;
    };
  } | null>(null);

  // Buffer status color mapping
  const bufferStatusColors: Record<string, string> = {
    'Late': '#f44336',      // Red
    'Warning': '#ff9800',   // Orange
    'Caution': '#9c27b0',   // Purple
    'OK': '#4caf50'         // Green
  };

  useEffect(() => {
    const fetchTasks = async () => {
      setIsLoading(true);
      setError(null);
      try {
        console.log('[GanttChart] Fetching task data from API...');
        const [ganttResponse, overviewResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/reports/gantt/priority-view?solver=${solver}`),
          fetch(`${API_BASE_URL}/reports/schedule-overview?solver=${solver}`)
        ]);
        
        if (!ganttResponse.ok) {
          throw new Error(`HTTP error! status: ${ganttResponse.status}`);
        }
        
        const data = await ganttResponse.json();
        console.log('[GanttChart] API response data:', data.length, 'tasks');
        
        if (data.length > 0) {
          // Log a sample task to inspect the date format
          console.log('[GanttChart] Sample task from API:', data[0]);
          
          // Check date ranges in the data to debug filtering issues
          const dates = data.map(task => [new Date(task.Start).getTime(), new Date(task.Finish).getTime()]);
          const validDates = dates.filter(([start, end]) => !isNaN(start) && !isNaN(end));
          
          if (validDates.length > 0) {
            const earliestDate = new Date(Math.min(...validDates.map(d => d[0])));
            const latestDate = new Date(Math.max(...validDates.map(d => d[1])));
            console.log('[GanttChart] Data date range:', {
              earliest: earliestDate.toISOString(),
              latest: latestDate.toISOString(),
              span: Math.round((latestDate.getTime() - earliestDate.getTime()) / (1000 * 60 * 60 * 24)) + ' days'
            });
          } else {
            console.warn('[GanttChart] No valid dates found in task data!');
          }
        } else {
          console.warn('[GanttChart] API returned empty task list');
        }
        
        setTasks(data);
        
        // Handle overview response
        if (overviewResponse.ok) {
          const overviewData = await overviewResponse.json();
          setOverview(overviewData);
        }
      } catch (e) {
        setError(`Failed to fetch task data: ${e instanceof Error ? e.message : String(e)}`);
        console.error('[GanttChart] Error fetching tasks:', e);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTasks();
  }, [solver]);

  // Sort tasks by job ID for consistency
  const sortedTasks = [...tasks].sort((a, b) => {
    const partsA = getTaskParts(a.Task);
    const partsB = getTaskParts(b.Task);

    // First, compare by jobGroup alphabetically ascending
    const jobCompare = partsA.jobGroup.localeCompare(partsB.jobGroup);
    if (jobCompare !== 0) {
      return jobCompare;
    }

    // If jobGroups are the same, sort by processNum descending
    // This makes P1 (smaller number) appear visually above P2 (larger number)
    // because Plotly puts higher index items at the top for horizontal bars.
    // So, if P1 should be "first" (top), it needs a higher effective sort order for this part.
    // partsB.processNum - partsA.processNum: if B(P1) num is 1, A(P2) num is 2 -> 1-2 = -1. A comes before B (P2, P1). This is correct.
    return partsB.processNum - partsA.processNum;
  });

  const taskTraces: Partial<PlotData>[] = [{
    type: 'bar',
    x: sortedTasks.map(task => {
      const start = new Date(task.Start);
      const end = new Date(task.Finish);
      return end.getTime() - start.getTime(); // Duration in milliseconds
    }),
    y: sortedTasks.map(task => task.Task),
    base: sortedTasks.map(task => new Date(task.Start).getTime()),
    orientation: 'h',
    marker: {
      color: sortedTasks.map(task => {
        // Use actual buffer status color only
        return task.Color || 
               (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]);
      })
    },
    text: sortedTasks.map(task => {
      const tooltipParts = [
        `<b>${task.Task}</b>`,
        `<b>Start:</b> ${task.Start}`,
        `<b>End:</b> ${task.Finish}`,
        `<b>Duration:</b> ${((new Date(task.Finish).getTime() - new Date(task.Start).getTime()) / (1000 * 3600)).toFixed(1)} hours`,
        `<b>Resource:</b> ${task.Resource}`,
        `<b>Priority:</b> ${task.PriorityLabel || 'Unknown'}`,
      ];
      if (task.JobFamily) {
        tooltipParts.push(`<b>Job Family:</b> ${task.JobFamily}`);
      }
      return tooltipParts.join('<br>');
    }),
    hoverinfo: 'text',
    name: 'Tasks'
  }];

  // Helper function to safely parse dates
  const parseDateSafely = (dateStr: string): Date | null => {
    if (!dateStr) return null;
    try {
      const date = new Date(dateStr);
      // Check if date is valid
      if (isNaN(date.getTime())) {
        return null;
      }
      return date;
    } catch {
      return null;
    }
  };
  
  const getTimeFilteredData = () => {
    // Use original data for all timeframes to avoid filtering issues
    if (timeRange === 'all' || sortedTasks.length === 0) {
      console.log('Using all tasks for "all" timeframe:', sortedTasks.length);
      
      // Even with "all", let's return a new array to avoid reference issues
      return [{
        type: 'bar',
        x: sortedTasks.map(task => {
          const start = new Date(task.Start);
          const end = new Date(task.Finish);
          return end.getTime() - start.getTime(); // Duration in milliseconds
        }),
        y: sortedTasks.map(task => task.Task),
        base: sortedTasks.map(task => new Date(task.Start).getTime()),
        orientation: 'h',
        marker: {
          color: sortedTasks.map(task => {
            return task.Color || 
                  (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]);
          })
        },
        text: sortedTasks.map(task => {
          const tooltipParts = [
            `<b>${task.Task}</b>`,
            `<b>Start:</b> ${task.Start}`,
            `<b>End:</b> ${task.Finish}`,
            `<b>Duration:</b> ${((new Date(task.Finish).getTime() - new Date(task.Start).getTime()) / (1000 * 3600)).toFixed(1)} hours`,
            `<b>Resource:</b> ${task.Resource}`,
            `<b>Priority:</b> ${task.PriorityLabel || 'Unknown'}`,
          ];
          if (task.JobFamily) {
            tooltipParts.push(`<b>Job Family:</b> ${task.JobFamily}`);
          }
          return tooltipParts.join('<br>');
        }),
        hoverinfo: 'text',
        name: 'Tasks'
      }];
    }
    
    const now = new Date();
    console.log('Current timeRange:', timeRange);
    console.log('Total tasks before filtering:', sortedTasks.length);
    
    // Find earliest and latest dates in the dataset to use as reference points
    const validDates = sortedTasks
      .map(task => [parseDateSafely(task.Start), parseDateSafely(task.Finish)])
      .filter(([start, end]) => start !== null && end !== null) as [Date, Date][];
    
    if (validDates.length === 0) {
      console.error('No valid dates found in task data');
      return [];
    }
    
    // Find earliest date in dataset
    const allTimestamps = validDates.flatMap(([start, end]) => [start.getTime(), end.getTime()]);
    const earliestDate = new Date(Math.min(...allTimestamps));
    const latestDate = new Date(Math.max(...allTimestamps));
    
    console.log('Dataset date range:', {
      earliest: earliestDate.toISOString(),
      latest: latestDate.toISOString(),
      span: Math.round((latestDate.getTime() - earliestDate.getTime()) / (1000 * 60 * 60 * 24)) + ' days'
    });
    
    // Always filter forward from today's date for time range selections
    let startDate = new Date(now);
    let endDate = new Date(now);
    
    console.log('Filtering forward from today for timeRange:', timeRange);
    
    // Set end date based on timeframe (forward from today)
    if (timeRange === '1d') {
      endDate.setDate(now.getDate() + 1);
    } else if (timeRange === '2d') {
      endDate.setDate(now.getDate() + 2);
    } else if (timeRange === '3d') {
      endDate.setDate(now.getDate() + 3);
    } else if (timeRange === '1w') {
      endDate.setDate(now.getDate() + 7);
    } else if (timeRange === '2w') {
      endDate.setDate(now.getDate() + 14);
    } else if (timeRange === '1m') {
      endDate.setMonth(now.getMonth() + 1);
    } else if (timeRange === '3m') {
      endDate.setMonth(now.getMonth() + 3);
    } else if (timeRange === '6m') {
      endDate.setMonth(now.getMonth() + 6);
    } else if (timeRange === '9m') {
      endDate.setMonth(now.getMonth() + 9);
    } else if (timeRange === '12m') {
      endDate.setFullYear(now.getFullYear() + 1);
    }
    
    console.log('Filter date range:', {
      start: startDate.toISOString(),
      end: endDate.toISOString()
    });
    
    // Filter tasks to include anything that falls within our date range
    const startTimestamp = startDate.getTime();
    const endTimestamp = endDate.getTime();
    
    const filteredTasks = sortedTasks.filter(task => {
      const taskStart = parseDateSafely(task.Start);
      const taskEnd = parseDateSafely(task.Finish);
      
      // Skip tasks with invalid dates
      if (!taskStart || !taskEnd) {
        console.warn('Task has invalid date format:', task.Task, task.Start, task.Finish);
        return false;
      }
      
      const taskStartTime = taskStart.getTime();
      const taskEndTime = taskEnd.getTime();
      
      // A task should be included if:
      // 1. It starts within our date range, OR
      // 2. It ends within our date range, OR
      // 3. It spans our date range (starts before and ends after)
      return (taskStartTime >= startTimestamp && taskStartTime <= endTimestamp) ||
             (taskEndTime >= startTimestamp && taskEndTime <= endTimestamp) ||
             (taskStartTime <= startTimestamp && taskEndTime >= endTimestamp);
    });
    
    console.log('Filtered tasks for', timeRange, ':', filteredTasks.length, 'of', sortedTasks.length);
    
    // If no tasks matched, show an empty chart rather than erroring
    if (filteredTasks.length === 0) {
      console.warn('No tasks passed the time filter for:', timeRange);
      return [];
    }
    
    return [{
      type: 'bar',
      x: filteredTasks.map(task => {
        const start = new Date(task.Start);
        const end = new Date(task.Finish);
        return end.getTime() - start.getTime(); // Duration in milliseconds
      }),
      y: filteredTasks.map(task => task.Task),
      base: filteredTasks.map(task => new Date(task.Start).getTime()),
      orientation: 'h',
              marker: {
          color: filteredTasks.map(task => {
            return task.Color || 
                  (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]);
          })
        },
      text: filteredTasks.map(task => {
        const tooltipParts = [
          `<b>${task.Task}</b>`,
          `<b>Start:</b> ${task.Start}`,
          `<b>End:</b> ${task.Finish}`,
          `<b>Duration:</b> ${((new Date(task.Finish).getTime() - new Date(task.Start).getTime()) / (1000 * 3600)).toFixed(1)} hours`,
          `<b>Resource:</b> ${task.Resource}`,
          `<b>Priority:</b> ${task.PriorityLabel || 'Unknown'}`,
        ];
        if (task.JobFamily) {
          tooltipParts.push(`<b>Job Family:</b> ${task.JobFamily}`);
        }
        return tooltipParts.join('<br>');
      }),
      hoverinfo: 'text',
      name: 'Tasks'
    }];
  };

  const layout = {
    title: chartTitle,
    height: Math.max(700, tasks.length * 30 + 150), // Dynamic height based on number of tasks
    width: window.innerWidth * 0.95, // Responsive width
    xaxis: {
      type: 'date' as const,
      title: 'Timeline',
      gridcolor: 'rgb(230, 230, 230)',
      gridwidth: 1,
      tickformat: '%b %d',
      dtick: 86400000,
      tickangle: -45,
      automargin: true,
    },
    yaxis: {
      title: 'Jobs',
      automargin: true,
      gridcolor: 'rgb(230, 230, 230)',
      gridwidth: 1,
    },
    autosize: true,
    margin: { l: 180, r: 50, t: 50, b: 100 }, // Increase left margin for job IDs
    plot_bgcolor: 'rgb(255, 255, 255)',
    paper_bgcolor: 'rgb(255, 255, 255)',
    showlegend: false,
    shapes: [] as any[],
  };

  // Calculate layout based on filtered tasks
  const calculateFilteredLayout = () => {
    // For "all" timeframe, calculate actual data range
    if (timeRange === 'all') {
      // Calculate the actual data range for 'all' timeframe
      const allValidDates = sortedTasks
        .map(task => [parseDateSafely(task.Start), parseDateSafely(task.Finish)])
        .filter(([start, end]) => start !== null && end !== null) as [Date, Date][];
      
      let xAxisConfig;
      if (allValidDates.length > 0) {
        const allTimestamps = allValidDates.flatMap(([start, end]) => [start.getTime(), end.getTime()]);
        const minDate = new Date(Math.min(...allTimestamps));
        const maxDate = new Date(Math.max(...allTimestamps));
        const xAxisRange = [minDate.toISOString(), maxDate.toISOString()];
        
        // Check if data spans less than 2 days, use hour format
        const timeSpanHours = (maxDate.getTime() - minDate.getTime()) / (1000 * 60 * 60);
        if (timeSpanHours <= 48) {
          xAxisConfig = {
            ...layout.xaxis,
            range: xAxisRange,
            tickformat: '%H:%M', // Show hours like "08:00"
            dtick: 3600000 * 2, // 2-hour intervals for short data
          };
        } else {
          xAxisConfig = {
            ...layout.xaxis,
            range: xAxisRange,
            tickformat: '%b %d', // Show dates like "May 30"
            dtick: 86400000, // Daily intervals
          };
        }
      } else {
        xAxisConfig = {
          ...layout.xaxis,
        };
      }
      
      return {
        ...layout,
        height: Math.max(700, sortedTasks.length * 30 + 150),
        xaxis: xAxisConfig,
        shapes: [{
          type: 'line',
          x0: new Date().toISOString(),
          y0: -0.5,
          x1: new Date().toISOString(),
          y1: sortedTasks.length > 0 ? sortedTasks.length - 0.5 : 10,
          line: {
            color: 'red',
            width: 2,
            dash: 'dash'
          }
        }]
      };
    }
    
    const now = new Date();
    
    // Find earliest and latest dates in the dataset to use as reference points
    const validDates = sortedTasks
      .map(task => [parseDateSafely(task.Start), parseDateSafely(task.Finish)])
      .filter(([start, end]) => start !== null && end !== null) as [Date, Date][];
      
    if (validDates.length === 0) {
      return {
        ...layout,
        height: 700,
        shapes: [{
          type: 'line',
          x0: new Date().toISOString(),
          y0: -0.5,
          x1: new Date().toISOString(),
          y1: 10,
          line: {
            color: 'red',
            width: 2,
            dash: 'dash'
          }
        }]
      };
    }
    
    // Always calculate ranges forward from today's date for time range selections
    let startDate = new Date(now);
    let endDate = new Date(now);
    
    // Set end date based on timeframe (forward from today)
    if (timeRange === '1d') {
      endDate.setDate(now.getDate() + 1);
    } else if (timeRange === '2d') {
      endDate.setDate(now.getDate() + 2);
    } else if (timeRange === '3d') {
      endDate.setDate(now.getDate() + 3);
    } else if (timeRange === '1w') {
      endDate.setDate(now.getDate() + 7);
    } else if (timeRange === '2w') {
      endDate.setDate(now.getDate() + 14);
    } else if (timeRange === '1m') {
      endDate.setMonth(now.getMonth() + 1);
    } else if (timeRange === '3m') {
      endDate.setMonth(now.getMonth() + 3);
    } else if (timeRange === '6m') {
      endDate.setMonth(now.getMonth() + 6);
    } else if (timeRange === '9m') {
      endDate.setMonth(now.getMonth() + 9);
    } else if (timeRange === '12m') {
      endDate.setFullYear(now.getFullYear() + 1);
    }
    
    // Filter tasks with the same logic we use in getTimeFilteredData
    const startTimestamp = startDate.getTime();
    const endTimestamp = endDate.getTime();
    
    const filteredTasksForLayout = sortedTasks.filter(task => {
      const taskStart = parseDateSafely(task.Start);
      const taskEnd = parseDateSafely(task.Finish);
      
      if (!taskStart || !taskEnd) {
        return false;
      }
      
      const taskStartTime = taskStart.getTime();
      const taskEndTime = taskEnd.getTime();
      
      return (taskStartTime >= startTimestamp && taskStartTime <= endTimestamp) ||
             (taskEndTime >= startTimestamp && taskEndTime <= endTimestamp) ||
             (taskStartTime <= startTimestamp && taskEndTime >= endTimestamp);
    });
    
    // Ensure we have reasonable height even with few tasks
    const adjustedHeight = Math.max(700, filteredTasksForLayout.length * 30 + 150);
    
    // Set the x-axis range to show our filtered window
    const xAxisRange = [startDate.toISOString(), endDate.toISOString()];
    
    // Configure x-axis format based on timeframe
    let xAxisConfig;
    if (['1d', '2d', '3d'].includes(timeRange)) {
      // For short timeframes, show hours
      xAxisConfig = {
        ...layout.xaxis,
        range: xAxisRange,
        tickformat: '%H:%M', // Show hours like "08:00"
        dtick: 3600000 * 4, // 4-hour intervals
      };
    } else {
      // For longer timeframes, show dates
      xAxisConfig = {
        ...layout.xaxis,
        range: xAxisRange,
        tickformat: '%b %d', // Show dates like "May 30"
        dtick: 86400000, // Daily intervals
      };
    }
    
    return {
      ...layout,
      height: adjustedHeight,
      xaxis: xAxisConfig,
      shapes: [{
        type: 'line',
        x0: new Date().toISOString(),
        y0: -0.5,
        x1: new Date().toISOString(),
        y1: filteredTasksForLayout.length > 0 ? filteredTasksForLayout.length - 0.5 : 10,
        line: {
          color: 'red',
          width: 2,
          dash: 'dash'
        }
      }]
    };
  };
  
  // Get the adjusted layout based on filtered tasks
  const adjustedLayout = calculateFilteredLayout();

  const handleTimeRangeChange = (range: string) => {
    if (range !== timeRange) {
      setTimeRange(range);
      // No loading state toggle to prevent blinking
    }
  };

  return (
    <div className="gantt-container">
      <button 
        className="back-button" 
        onClick={() => window.history.back()}
      >
        <i className="fas fa-arrow-left"></i> Back
      </button>
      <div className="flat-time-selector">
        <div className="flat-button-group">
          <button 
            className={timeRange === '1d' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('1d')}
            style={{width: '55px'}}
          >1d</button>
          <button 
            className={timeRange === '2d' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('2d')}
            style={{width: '55px'}}
          >2d</button>
          <button 
            className={timeRange === '3d' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('3d')}
            style={{width: '55px'}}
          >3d</button>
          <button 
            className={timeRange === '1w' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('1w')}
            style={{width: '55px'}}
          >1w</button>
          <button 
            className={timeRange === '2w' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('2w')}
            style={{width: '55px'}}
          >2w</button>
          <button 
            className={timeRange === '1m' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('1m')}
            style={{width: '55px'}}
          >1m</button>
          <button 
            className={timeRange === '3m' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('3m')}
            style={{width: '55px'}}
          >3m</button>
          <button 
            className={timeRange === '6m' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('6m')}
            style={{width: '55px'}}
          >6m</button>
          <button 
            className={timeRange === '9m' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('9m')}
            style={{width: '55px'}}
          >9m</button>
          <button 
            className={timeRange === '12m' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('12m')}
            style={{width: '55px'}}
          >12m</button>
          <button 
            className={timeRange === 'all' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('all')}
            style={{width: '55px'}}
          >all</button>
        </div>
      </div>
      
      {overview && (
        <div className="overview-section">
          <div className="overview-left">
            <h3>Schedule Overview</h3>
            <div className="overview-stats">
              <div className="stat-item">
                <span className="stat-label">Total Jobs:</span>
                <span className="stat-value">{overview.total_jobs}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Date Range:</span>
                <span className="stat-value">N/A</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Total Duration:</span>
                <span className="stat-value">0 hours</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Records Displayed:</span>
                <span className="stat-value">{overview.total_jobs}</span>
              </div>
            </div>
          </div>
          
          <div className="overview-right">
            <h3>Buffer Status</h3>
            <div className="buffer-overview">
              <div className="buffer-rows">
                <div className="buffer-row">
                  <div className="buffer-label buffer-label-late">Late</div>
                  <div className="buffer-bar-container">
                    <div 
                      className="buffer-bar-fill buffer-late" 
                      style={{ width: `${(overview.buffer_status_counts.Late / overview.total_jobs) * 100}%` }}
                    >
                      <span className="buffer-count">{overview.buffer_status_counts.Late} jobs</span>
                    </div>
                  </div>
                </div>
                
                <div className="buffer-row">
                  <div className="buffer-label buffer-label-warning">Warning</div>
                  <div className="buffer-bar-container">
                    <div 
                      className="buffer-bar-fill buffer-warning" 
                      style={{ width: `${(overview.buffer_status_counts.Warning / overview.total_jobs) * 100}%` }}
                    >
                      <span className="buffer-count">{overview.buffer_status_counts.Warning} jobs</span>
                    </div>
                  </div>
                </div>
                
                <div className="buffer-row">
                  <div className="buffer-label buffer-label-caution">Caution</div>
                  <div className="buffer-bar-container">
                    <div 
                      className="buffer-bar-fill buffer-caution" 
                      style={{ width: `${(overview.buffer_status_counts.Caution / overview.total_jobs) * 100}%` }}
                    >
                      <span className="buffer-count">{overview.buffer_status_counts.Caution} jobs</span>
                    </div>
                  </div>
                </div>
                
                <div className="buffer-row">
                  <div className="buffer-label buffer-label-ok">OK</div>
                  <div className="buffer-bar-container">
                    <div 
                      className="buffer-bar-fill buffer-ok" 
                      style={{ width: `${(overview.buffer_status_counts.OK / overview.total_jobs) * 100}%` }}
                    >
                      <span className="buffer-count">{overview.buffer_status_counts.OK} jobs</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="priority-legend">
        <div className="priority-item">
          <span className="priority-color" style={{ backgroundColor: '#f44336' }}></span>
          <span className="priority-label">Late (&lt;0h)</span>
        </div>
        <div className="priority-item">
          <span className="priority-color" style={{ backgroundColor: '#ff9800' }}></span>
          <span className="priority-label">Warning (&lt;24h)</span>
        </div>
        <div className="priority-item">
          <span className="priority-color" style={{ backgroundColor: '#9c27b0' }}></span>
          <span className="priority-label">Caution (&lt;72h)</span>
        </div>
        <div className="priority-item">
          <span className="priority-color" style={{ backgroundColor: '#4caf50' }}></span>
          <span className="priority-label">OK (&gt;72h)</span>
        </div>
      </div>

      {isLoading && <div className="loading">Loading chart data...</div>}
      {error && <div className="error">{error}</div>}
      
      {!isLoading && !error && (
        <Plot
          data={getTimeFilteredData()}
          layout={adjustedLayout}
          config={{ responsive: true }}
        />
      )}
    </div>
  );
};

export default GanttChartDisplay; 