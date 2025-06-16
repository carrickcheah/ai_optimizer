import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { PlotData } from 'plotly.js';
import { useDataCache } from '../contexts/DataCacheContext';
import './resource_chart.css'; // Import the CSS file for this component

interface TaskData {
  Task: string;      // Represents the unique task identifier (e.g., UNIQUE_JOB_ID)
  Start: string;
  Finish: string;
  Resource: string;  // Machine or resource responsible for the task
  PriorityInteger?: number;
  PriorityLabel?: string;
  Color?: string;
  Description?: string;
  JobFamily?: string;
  ProcessNumber?: number;
  BufferStatusLabel?: string;
}

interface ResourceChartProps {
  title?: string;
}

const ResourceChart: React.FC<ResourceChartProps> = ({ title }) => {
  const { data } = useDataCache();
  const [timeRange, setTimeRange] = useState<string>('all');

  // Use cached data instead of local state
  const tasks: TaskData[] = data.ganttResourceView;
  const isLoading = data.isLoading;
  const error = data.error;
  const overview = data.scheduleOverview;



  // Helper function to format datetime for display
  const formatDateTime = (dateTimeString: string): string => {
    try {
      const date = new Date(dateTimeString);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      
      return `${year}-${month}-${day} | ${hours}:${minutes}`;
    } catch (error) {
      return dateTimeString; // Fallback to original if parsing fails
    }
  };

  // No automatic data loading - user must click refresh button
  
  // Log data when available  
  useEffect(() => {
    if (tasks.length > 0) {
      console.log('[ResourceChart] Using cached data:', tasks.length, 'tasks');
      
      // Log a sample task to inspect the date format
      console.log('[ResourceChart] Sample task from cache:', tasks[0]);
      
      // Calculate date range from the cached data
      const dates = tasks.flatMap(task => [
        new Date(task.Start),
        new Date(task.Finish)
      ]).filter(date => !isNaN(date.getTime()));
      
      if (dates.length > 0) {
        const minDate = new Date(Math.min(...dates.map(d => d.getTime())));
        let maxDate = new Date(Math.max(...dates.map(d => d.getTime())));
        
        console.log('[ResourceChart] Data date range:', {
          earliest: minDate.toISOString(),
          latest: maxDate.toISOString(),
          span: Math.round((maxDate.getTime() - minDate.getTime()) / (1000 * 60 * 60 * 24)) + ' days'
        });
        
        // Ensure date range is at most 1 year
        const oneYearFromMin = new Date(minDate);
        oneYearFromMin.setFullYear(oneYearFromMin.getFullYear() + 1);
        
        if (maxDate > oneYearFromMin) {
          console.log('[ResourceChart] Limiting max date to one year from min date');
          maxDate = oneYearFromMin;
        }
        

      } else {
        console.warn('[ResourceChart] No valid dates found in cached data!');
      }
    } else if (!isLoading) {
      console.warn('[ResourceChart] No cached data available');
    }
  }, [tasks, isLoading]);



  // Filter out subcontractor tasks and sort by resource, then by start time
  const machineOnlyTasks = tasks.filter(task => task.Resource !== 'Subcon');
  const sortedTasks = [...machineOnlyTasks].sort((a, b) => {
    if (a.Resource !== b.Resource) {
      return a.Resource.localeCompare(b.Resource);
    }
    return new Date(a.Start).getTime() - new Date(b.Start).getTime();
  });

  // Simple alphabetical sorting for machine resources only
  const sortMachineResources = (resources: string[]): string[] => {
    return resources.sort((a, b) => a.localeCompare(b));
  };

  const resourceGroups = sortMachineResources([...new Set(sortedTasks.map(task => task.Resource))]);
  
  console.log('[ResourceChart] Sorted tasks:', sortedTasks.length);
  console.log('[ResourceChart] Resource groups:', resourceGroups);
  
  // Buffer status color mapping
  const bufferStatusColors: Record<string, string> = {
    'Late': '#f44336',      // Red
    'Warning': '#ff9800',   // Orange
    'Caution': '#9c27b0',   // Purple
    'OK': '#7FFF00'         // Bright lime green
  };
  
  const plotData: Partial<PlotData>[] = [];
  
  resourceGroups.forEach(resource => {
    const resourceTasks = sortedTasks.filter(task => task.Resource === resource);
    
    console.log(`[ResourceChart] Resource ${resource}: ${resourceTasks.length} tasks`);
    
    plotData.push({
      type: 'bar',
      name: resource, // Legend entry for this machine
      x: resourceTasks.map(task => {
        const start = new Date(task.Start);
        const end = new Date(task.Finish);
        return end.getTime() - start.getTime(); // Duration in milliseconds
      }),
                  y: resourceTasks.map(() => resource), // Y-value is the machine name
      base: resourceTasks.map(task => new Date(task.Start).getTime()),
      orientation: 'h',
      marker: {
        color: resourceTasks.map(task => {
          // Use buffer status color only (ignore task.Color)
          return (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]) || '#cccccc';
        })
      },
      text: resourceTasks.map(task => {
        const tooltipParts = [
          `<b>${task.Task}</b>${task.JobFamily ? ` (${task.JobFamily})` : ''}`,
          `<b>Machine:</b> ${task.Resource}`,
          `<b>Start:</b> ${formatDateTime(task.Start)}`,
          `<b>End:</b> ${formatDateTime(task.Finish)}`,
          `<b>Duration:</b> ${((new Date(task.Finish).getTime() - new Date(task.Start).getTime()) / (1000 * 3600)).toFixed(1)} hours`
        ];
        return tooltipParts.join('<br>');
      }),
      hoverinfo: 'text',
      showlegend: false
    } as any);
  });

  console.log('[ResourceChart] Generated plotData:', plotData.length, 'series');
  console.log('[ResourceChart] Sample plotData entry:', plotData[0]);
  
  // Debug the actual chart data values
  if (plotData.length > 0 && plotData[0]) {
    console.log('[ResourceChart] First series x values (durations):', plotData[0].x);
    console.log('[ResourceChart] First series y values (resources):', plotData[0].y);
    console.log('[ResourceChart] First series base values (start times):', (plotData[0] as any).base);
  }

  const chartTitle = title || 'Production Planning System (by Resource)';
  
  const handleTimeRangeChange = (range: string) => {
    if (range !== timeRange) {
      setTimeRange(range);
      // No loading state toggle to prevent blinking
    }
  };

  // CP-SAT solver is always used

  if (isLoading) {
    return (
      <div className="p-4 bg-white shadow-md rounded-lg loading-container">
        <div className="spinner"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-white shadow-md rounded-lg">
        <div className="error-message">Error loading chart data: {error}</div>
      </div>
    );
  }

  if (!isLoading && tasks.length === 0) {
    return (
      <div className="gantt-container">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <button 
            className="back-button" 
            onClick={() => window.history.back()}
          >
            <i className="fas fa-arrow-left"></i> Back
          </button>

        </div>
        <div className="text-center p-4">
          <h3>No Data Available</h3>
          <p>Click the "Load Data" button above to load schedule data.</p>
          <p><small>Data will be shared across all pages once loaded.</small></p>
        </div>
      </div>
    );
  }

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
    // If timeframe is 'all' or we have no tasks, return complete data
    if (timeRange === 'all' || sortedTasks.length === 0) {
      console.log('[ResourceChart] Using all tasks for "all" timeframe:', sortedTasks.length);
      console.log('[ResourceChart] Returning plotData with', plotData.length, 'series');
      return plotData; // Return the default plotData
    }
    
    const now = new Date();
    console.log('[ResourceChart] Current timeRange:', timeRange);
    console.log('[ResourceChart] Total tasks before filtering:', sortedTasks.length);
    
    // Find earliest and latest dates in the dataset to use as reference points
    const validDates = sortedTasks
      .map(task => [parseDateSafely(task.Start), parseDateSafely(task.Finish)])
      .filter(([start, end]) => start !== null && end !== null) as [Date, Date][];
    
    if (validDates.length === 0) {
      console.error('[ResourceChart] No valid dates found in task data');
      return [];
    }
    
    // Find earliest date in dataset
    const allTimestamps = validDates.flatMap(([start, end]) => [start.getTime(), end.getTime()]);
    const earliestDate = new Date(Math.min(...allTimestamps));
    const latestDate = new Date(Math.max(...allTimestamps));
    
    console.log('[ResourceChart] Dataset date range:', {
      earliest: earliestDate.toISOString(),
      latest: latestDate.toISOString(),
      span: Math.round((latestDate.getTime() - earliestDate.getTime()) / (1000 * 60 * 60 * 24)) + ' days'
    });
    
    // Always filter forward from today's date for time range selections
    let startDate = new Date(now);
    let endDate = new Date(now);
    
    console.log('[ResourceChart] Filtering forward from today for timeRange:', timeRange);
    
    // Set end date based on timeframe (forward from today)
    if (timeRange === '1d') {
      endDate.setDate(now.getDate() + 1);
    } else if (timeRange === '2d') {
      endDate.setDate(now.getDate() + 2);
    } else if (timeRange === '3d') {
      endDate.setDate(now.getDate() + 3);
    } else if (timeRange === '4d') {
      endDate.setDate(now.getDate() + 4);
    } else if (timeRange === '5d') {
      endDate.setDate(now.getDate() + 5);
    } else if (timeRange === '7d') {
      endDate.setDate(now.getDate() + 7);
    } else if (timeRange === '14d') {
      endDate.setDate(now.getDate() + 14);
    } else if (timeRange === '21d') {
      endDate.setDate(now.getDate() + 21);
    } else if (timeRange === '1m') {
      endDate.setMonth(now.getMonth() + 1);
    } else if (timeRange === '2m') {
      endDate.setMonth(now.getMonth() + 2);
    } else if (timeRange === '3m') {
      endDate.setMonth(now.getMonth() + 3);
    }
    
    console.log('[ResourceChart] Filter date range:', {
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
        console.warn('[ResourceChart] Task has invalid date format:', task.Task, task.Start, task.Finish);
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
    
    console.log('[ResourceChart] Filtered tasks for', timeRange, ':', filteredTasks.length, 'of', sortedTasks.length);
    
    // If no tasks matched, show an empty chart rather than erroring
    if (filteredTasks.length === 0) {
      console.warn('[ResourceChart] No tasks passed the time filter for:', timeRange);
      return [];
    }
    
    // Create filtered plotData
    const filteredPlotData: Partial<PlotData>[] = [];
    
    // Get unique resources from filtered tasks
    const filteredResourceGroups = sortMachineResources([...new Set(filteredTasks.map(task => task.Resource))]);
    
    filteredResourceGroups.forEach(resource => {
      const resourceTasks = filteredTasks.filter(task => task.Resource === resource);
      
      if (resourceTasks.length > 0) {
        filteredPlotData.push({
          type: 'bar',
          name: resource, // Legend entry for this machine
          x: resourceTasks.map(task => {
            const start = new Date(task.Start);
            const end = new Date(task.Finish);
            return end.getTime() - start.getTime(); // Duration in milliseconds
          }),
          y: resourceTasks.map(() => resource), // Y-value is the machine name
          base: resourceTasks.map(task => new Date(task.Start).getTime()),
          orientation: 'h',
          marker: {
            color: resourceTasks.map(task => {
              // Use buffer status color only (ignore task.Color)
              return (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]) || '#cccccc';
            })
          },
          text: resourceTasks.map(task => {
            const tooltipParts = [
              `<b>${task.Task}</b>${task.JobFamily ? ` (${task.JobFamily})` : ''}`,
              `<b>Machine:</b> ${task.Resource}`,
              `<b>Start:</b> ${formatDateTime(task.Start)}`,
              `<b>End:</b> ${formatDateTime(task.Finish)}`,
              `<b>Duration:</b> ${((new Date(task.Finish).getTime() - new Date(task.Start).getTime()) / (1000 * 3600)).toFixed(1)} hours`
            ];
            return tooltipParts.join('<br>');
          }),
          hoverinfo: 'text',
          showlegend: false
        } as any);
      }
    });
    
    return filteredPlotData;
  };

  const layout = {
    title: chartTitle,
    height: Math.max(700, resourceGroups.length * 50 + 200), // Adjusted height for resource groups
    width: window.innerWidth * 0.95,
    xaxis: {
      type: 'date' as const,
      title: 'Timeline (SGT)',
      gridcolor: 'rgb(230, 230, 230)',
      gridwidth: 1,
      tickformat: '%b %d',
      dtick: 86400000,
      tickangle: -45,
      automargin: true,
      // Force timezone to be consistent with backend (Singapore)
      timezone: 'Asia/Singapore',
    },
    yaxis: {
      title: 'Machine Name', 
      type: 'category',
      automargin: true,
      gridcolor: 'rgb(230, 230, 230)',
      gridwidth: 1,
      categoryorder: 'array' as const,
      categoryarray: sortMachineResources([...resourceGroups]),
      autorange: 'reversed' as const,
    },
    autosize: true,
    margin: { l: 180, r: 50, t: 50, b: 100 },
    plot_bgcolor: 'rgb(255, 255, 255)',
    paper_bgcolor: 'rgb(255, 255, 255)',
    showlegend: false,
    legend: {
      x: 1,
      y: 1,
      xanchor: 'right' as const,
    },
    barmode: 'stack' as const, // Stack bars for the same machine if they overlap (though base should prevent this for distinct tasks)
    shapes: [{
      type: 'line',
      x0: new Date().toISOString(),
      y0: -0.5,
      x1: new Date().toISOString(),
      y1: resourceGroups.length - 0.5,
      line: {
        color: 'red',
        width: 2,
        dash: 'dash'
      }
    }]
  };

  // Calculate layout based on filtered tasks
  const calculateFilteredLayout = () => {
    // For "all" timeframe, we can just use all tasks
    if (timeRange === 'all') {
      // Get all unique resources for the y-axis
      const allResourceGroups = sortMachineResources([...new Set(sortedTasks.map(task => task.Resource))]);
      
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
            dtick: 3600000, // 1-hour intervals (every hour)
            timezone: 'Asia/Singapore',
          };
        } else {
          xAxisConfig = {
            ...layout.xaxis,
            range: xAxisRange,
            tickformat: '%b %d', // Show dates like "May 30"
            dtick: 86400000, // Daily intervals
            timezone: 'Asia/Singapore',
          };
        }
      } else {
        xAxisConfig = {
          ...layout.xaxis,
        };
      }
      
      return {
        ...layout,
        height: Math.max(700, allResourceGroups.length * 50 + 200),
        xaxis: xAxisConfig,
        yaxis: {
          ...layout.yaxis,
          type: 'category',
          categoryorder: 'array' as const,
                  categoryarray: sortMachineResources([...allResourceGroups]),
          autorange: 'reversed' as const,
        },
        shapes: [{
          type: 'line',
          x0: new Date().toISOString(),
          y0: -0.5,
          x1: new Date().toISOString(),
          y1: allResourceGroups.length - 0.5,
          line: {
            color: 'red',
            width: 2,
            dash: 'dash'
          }
        }]
      };
    }
    
    const now = new Date();
    
    // Find earliest and latest dates in the dataset
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
          y1: resourceGroups.length - 0.5,
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
    } else if (timeRange === '4d') {
      endDate.setDate(now.getDate() + 4);
    } else if (timeRange === '5d') {
      endDate.setDate(now.getDate() + 5);
    } else if (timeRange === '7d') {
      endDate.setDate(now.getDate() + 7);
    } else if (timeRange === '14d') {
      endDate.setDate(now.getDate() + 14);
    } else if (timeRange === '21d') {
      endDate.setDate(now.getDate() + 21);
    } else if (timeRange === '1m') {
      endDate.setMonth(now.getMonth() + 1);
    } else if (timeRange === '2m') {
      endDate.setMonth(now.getMonth() + 2);
    } else if (timeRange === '3m') {
      endDate.setMonth(now.getMonth() + 3);
    }
    
    // Filter tasks to get resources that should be shown
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
    
    // Get unique resources from filtered tasks
    const filteredResourceGroups = sortMachineResources([...new Set(filteredTasksForLayout.map(task => task.Resource))]);
    
    // Set the x-axis range to show our filtered window
    const xAxisRange = [startDate.toISOString(), endDate.toISOString()];
    
    // Configure x-axis format based on timeframe
    let xAxisConfig;
    if (['1d', '2d', '3d', '4d', '5d'].includes(timeRange)) {
      // For short timeframes, show hours from 01:00 to 23:59
      xAxisConfig = {
        ...layout.xaxis,
        range: xAxisRange,
        tickformat: '%H:%M', // Show hours like "08:00"
        dtick: 3600000, // 1-hour intervals (every hour)
        timezone: 'Asia/Singapore',
      };
    } else {
      // For longer timeframes, show dates
      xAxisConfig = {
        ...layout.xaxis,
        range: xAxisRange,
        tickformat: '%b %d', // Show dates like "May 30"
        dtick: 86400000, // Daily intervals
        timezone: 'Asia/Singapore',
      };
    }
    
    return {
      ...layout,
      height: Math.max(700, filteredResourceGroups.length * 50 + 200),
      xaxis: xAxisConfig,
      yaxis: {
        ...layout.yaxis,
        type: 'category',
        categoryorder: 'array' as const,
        categoryarray: sortMachineResources([...filteredResourceGroups]),
        autorange: 'reversed' as const,
      },
      shapes: [{
        type: 'line',
        x0: new Date().toISOString(),
        y0: -0.5,
        x1: new Date().toISOString(),
        y1: filteredResourceGroups.length - 0.5,
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
  
  return (
    <div className="gantt-container">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <button 
          className="back-button" 
          onClick={() => window.history.back()}
        >
          <i className="fas fa-arrow-left"></i> Back
        </button>

      </div>
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
            className={timeRange === '4d' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('4d')}
            style={{width: '55px'}}
          >4d</button>
          <button 
            className={timeRange === '5d' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('5d')}
            style={{width: '55px'}}
          >5d</button>
          <button 
            className={timeRange === '7d' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('7d')}
            style={{width: '55px'}}
          >7d</button>
          <button 
            className={timeRange === '14d' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('14d')}
            style={{width: '55px'}}
          >14d</button>
          <button 
            className={timeRange === '21d' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('21d')}
            style={{width: '55px'}}
          >21d</button>
          <button 
            className={timeRange === '1m' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('1m')}
            style={{width: '55px'}}
          >1m</button>
          <button 
            className={timeRange === '2m' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('2m')}
            style={{width: '55px'}}
          >2m</button>
          <button 
            className={timeRange === '3m' ? 'flat-active' : 'flat-inactive'} 
            onClick={() => handleTimeRangeChange('3m')}
            style={{width: '55px'}}
          >3m</button>
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
                <span className="stat-value">{tasks.length}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Date Range:</span>
                <span className="stat-value">{
                  (() => {
                    if (tasks.length === 0) return 'N/A';
                    const dates = tasks.map(task => [new Date(task.Start), new Date(task.Finish)]).flat();
                    const validDates = dates.filter(date => !isNaN(date.getTime()));
                    if (validDates.length === 0) return 'N/A';
                    const earliest = new Date(Math.min(...validDates.map(d => d.getTime())));
                    const latest = new Date(Math.max(...validDates.map(d => d.getTime())));
                    const formatDate = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
                    return `${formatDate(earliest)} to ${formatDate(latest)}`;
                  })()
                }</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Total Duration:</span>
                <span className="stat-value">{
                  (() => {
                    if (tasks.length === 0) return '0 hours';
                    const totalDuration = tasks.reduce((total, task) => {
                      const start = new Date(task.Start);
                      const end = new Date(task.Finish);
                      if (isNaN(start.getTime()) || isNaN(end.getTime())) return total;
                      return total + (end.getTime() - start.getTime());
                    }, 0);
                    const totalHours = Math.round(totalDuration / (1000 * 60 * 60));
                    return `${totalHours.toLocaleString()} hours`;
                  })()
                }</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Records Displayed:</span>
                <span className="stat-value">{tasks.length}</span>
              </div>
            </div>
          </div>
          
          <div className="overview-right">
            <h3>Buffer Status</h3>
            <div className="buffer-overview">
              <div className="buffer-rows">
                {(() => {
                  // Calculate actual buffer status counts from tasks
                  const bufferCounts = {
                    Late: tasks.filter(task => task.BufferStatusLabel === 'Late').length,
                    Warning: tasks.filter(task => task.BufferStatusLabel === 'Warning').length,
                    Caution: tasks.filter(task => task.BufferStatusLabel === 'Caution').length,
                    OK: tasks.filter(task => task.BufferStatusLabel === 'OK').length
                  };
                  const totalTasks = tasks.length || 1; // Avoid division by zero
                  
                  return (
                    <>
                      <div className="buffer-row">
                        <div className="buffer-label buffer-label-late">Late</div>
                        <div className="buffer-bar-container">
                          <div 
                            className="buffer-bar-fill buffer-late" 
                            style={{ width: `${(bufferCounts.Late / totalTasks) * 100}%` }}
                          >
                            <span className="buffer-count">{bufferCounts.Late} jobs</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="buffer-row">
                        <div className="buffer-label buffer-label-warning">Warning</div>
                        <div className="buffer-bar-container">
                          <div 
                            className="buffer-bar-fill buffer-warning" 
                            style={{ width: `${(bufferCounts.Warning / totalTasks) * 100}%` }}
                          >
                            <span className="buffer-count">{bufferCounts.Warning} jobs</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="buffer-row">
                        <div className="buffer-label buffer-label-caution">Caution</div>
                        <div className="buffer-bar-container">
                          <div 
                            className="buffer-bar-fill buffer-caution" 
                            style={{ width: `${(bufferCounts.Caution / totalTasks) * 100}%` }}
                          >
                            <span className="buffer-count">{bufferCounts.Caution} jobs</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="buffer-row">
                        <div className="buffer-label buffer-label-ok">OK</div>
                        <div className="buffer-bar-container">
                          <div 
                            className="buffer-bar-fill buffer-ok" 
                            style={{ width: `${(bufferCounts.OK / totalTasks) * 100}%` }}
                          >
                            <span className="buffer-count">{bufferCounts.OK} jobs</span>
                          </div>
                        </div>
                      </div>
                    </>
                  );
                })()}
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
                          <span className="priority-color" style={{ backgroundColor: '#7FFF00' }}></span>
          <span className="priority-label">OK (&gt;72h)</span>
        </div>
      </div>

      {isLoading && <div className="loading">Loading chart data...</div>}
      {error && <div className="error">{error}</div>}
      
      {!isLoading && !error && (
        <Plot
          data={getTimeFilteredData()}
          layout={adjustedLayout as any} // Cast to any to handle Plotly type complexities with categoryarray etc.
          config={{ responsive: true }}
        />
      )}
    </div>
  );
};

export default ResourceChart;
