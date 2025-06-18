import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { useDataCache } from '../contexts/DataCacheContext';
import { useWorkingHours, timeToMinutes, minutesToTime, isTimeInWorkingPeriod, isTimeInBreak, WorkingHour, BreakTime } from '../hooks/useWorkingHours';
import './GanttChartDisplay.css'; // Import the CSS file



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





const GanttChartDisplay: React.FC = () => {
  const { data } = useDataCache();
  const { config: workingHoursConfig, isLoading: workingHoursLoading, error: workingHoursError } = useWorkingHours();
  const [timeRange, setTimeRange] = useState<string>('all');
  const [chartTitle] = useState<string>('Production Planning System');

  // Use cached data instead of local state
  const tasks = data.ganttPriorityView;
  const isLoading = data.isLoading || workingHoursLoading;
  const error = data.error || workingHoursError;
  const overview = data.scheduleOverview;

  // Buffer status color mapping
  const bufferStatusColors: Record<string, string> = {
    'Late': '#f44336',      // Red
    'Warning': '#ff9800',   // Orange
    'Caution': '#9c27b0',   // Purple
    'OK': '#7FFF00'         // Bright lime green
  };

  // No automatic data loading - user must click refresh button

  // Log data when available
  useEffect(() => {
    if (tasks.length > 0) {
      console.log('[GanttChart] Using cached data:', tasks.length, 'tasks');
      
      // Log a sample task to inspect the date format
      console.log('[GanttChart] Sample task from cache:', tasks[0]);
      
      // Check date ranges in the data
      const dates = tasks.map(task => [new Date(task.Start).getTime(), new Date(task.Finish).getTime()]);
      const validDates = dates.filter(([start, end]) => !isNaN(start) && !isNaN(end));
      
      if (validDates.length > 0) {
        const earliestDate = new Date(Math.min(...validDates.map(d => d[0])));
        const latestDate = new Date(Math.max(...validDates.map(d => d[1])));
        console.log('[GanttChart] Data date range:', {
          earliest: earliestDate.toISOString(),
          latest: latestDate.toISOString(),
          span: Math.round((latestDate.getTime() - earliestDate.getTime()) / (1000 * 60 * 60 * 24)) + ' days'
        });
      }
    } else if (!isLoading) {
      console.warn('[GanttChart] No cached data available');
    }
  }, [tasks, isLoading]);



  // Create task segments with dynamic working hours and break gaps
  const createTaskSegmentsWithBreaks = (task: any) => {
    // If working hours config is not available, return original task without segmentation
    if (!workingHoursConfig) {
      console.warn('Working hours configuration not available, using original task without segmentation');
      return [task];
    }

    const startTime = new Date(task.Start);
    const endTime = new Date(task.Finish);
    const segments = [];
    
    let currentTime = new Date(startTime);
    let segmentIndex = 0;
    
    while (currentTime < endTime) {
      const dayOfWeek = currentTime.getDay(); // 0 = Sunday, 1 = Monday, etc.
      const dayKey = dayOfWeek.toString();
      
      // Get working hours for this day of week
      const dayWorkingHours = workingHoursConfig.working_hours_by_day[dayKey] || [];
      
      if (dayWorkingHours.length === 0) {
        // No working hours for this day, move to next day
        currentTime.setDate(currentTime.getDate() + 1);
        currentTime.setHours(0, 0, 0, 0);
        continue;
      }
      
      // Get current time in minutes since midnight
      const currentMinutes = currentTime.getHours() * 60 + currentTime.getMinutes();
      
      // Find next available working period
      let nextWorkingPeriod: WorkingHour | null = null;
      let nextWorkingStart = 0;
      
      for (const workingHour of dayWorkingHours) {
        if (!workingHour.is_working) continue;
        
        const periodStart = timeToMinutes(workingHour.start_time);
        const periodEnd = timeToMinutes(workingHour.end_time);
        
        if (currentMinutes < periodEnd) {
          nextWorkingPeriod = workingHour;
          nextWorkingStart = Math.max(currentMinutes, periodStart);
          break;
        }
      }
      
      if (!nextWorkingPeriod) {
        // No more working periods today, move to next day
        currentTime.setDate(currentTime.getDate() + 1);
        currentTime.setHours(0, 0, 0, 0);
        continue;
      }
      
      // Set segment start time
      const segmentStartMinutes = nextWorkingStart;
      const segmentStart = new Date(currentTime);
      segmentStart.setHours(Math.floor(segmentStartMinutes / 60), segmentStartMinutes % 60, 0, 0);
      
      // Find segment end time (limited by working period, breaks, or task end)
      const workingPeriodEnd = timeToMinutes(nextWorkingPeriod.end_time);
      let segmentEndMinutes = Math.min(workingPeriodEnd, 
        endTime.getDate() === currentTime.getDate() && 
        endTime.getFullYear() === currentTime.getFullYear() && 
        endTime.getMonth() === currentTime.getMonth() ? 
        endTime.getHours() * 60 + endTime.getMinutes() : workingPeriodEnd);
      
      // Check for breaks that intersect with this segment
      for (const breakTime of workingHoursConfig.break_times) {
        const breakStart = timeToMinutes(breakTime.start_time);
        const breakEnd = timeToMinutes(breakTime.end_time);
        
        // If break starts within our segment, end segment at break start
        if (breakStart > segmentStartMinutes && breakStart < segmentEndMinutes) {
          segmentEndMinutes = breakStart;
          break;
        }
      }
      
      const segmentEnd = new Date(currentTime);
      segmentEnd.setHours(Math.floor(segmentEndMinutes / 60), segmentEndMinutes % 60, 0, 0);
      
      // Create segment if it has meaningful duration (at least 1 minute)
      if (segmentEnd.getTime() - segmentStart.getTime() >= 60000) {
        segments.push({
          ...task,
          Task: `${task.Task}_seg${segmentIndex}`,
          Start: segmentStart.toISOString(),
          Finish: segmentEnd.toISOString()
        });
        segmentIndex++;
      }
      
      // Move current time forward
      if (segmentEnd >= endTime) {
        // Task is complete
        break;
      } else if (segmentEndMinutes >= workingPeriodEnd) {
        // Working period ended, check for next period or next day
        let foundNextPeriod = false;
        for (const workingHour of dayWorkingHours) {
          if (!workingHour.is_working) continue;
          const periodStart = timeToMinutes(workingHour.start_time);
          if (periodStart > segmentEndMinutes) {
            currentTime.setHours(Math.floor(periodStart / 60), periodStart % 60, 0, 0);
            foundNextPeriod = true;
            break;
          }
        }
        
        if (!foundNextPeriod) {
          // No more working periods today, move to next day
          currentTime.setDate(currentTime.getDate() + 1);
          currentTime.setHours(0, 0, 0, 0);
        }
      } else {
        // We hit a break or task end, advance to after the break
        const breakTime = isTimeInBreak(segmentEndMinutes, workingHoursConfig.break_times);
        if (breakTime) {
          const breakEndMinutes = timeToMinutes(breakTime.end_time);
          currentTime.setHours(Math.floor(breakEndMinutes / 60), breakEndMinutes % 60, 0, 0);
        } else {
          // Task ended
          break;
        }
      }
    }
    
    return segments.length > 0 ? segments : [task];
  };
  
  // Apply break segmentation to tasks
  const segmentedTasks = tasks.flatMap(task => {
    const duration = new Date(task.Finish).getTime() - new Date(task.Start).getTime();
    const hoursDuration = duration / (1000 * 60 * 60);
    
    // Only segment tasks longer than 4 hours (likely to span breaks)
    if (hoursDuration > 4) {
      return createTaskSegmentsWithBreaks(task);
    }
    return [task];
  });
  
  // Sort tasks by job ID for consistency
  const sortedTasks = [...segmentedTasks].sort((a, b) => {
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
            // For subcontractor tasks, use a distinct pattern by modifying the color
            if (task.Resource === 'Subcon') {
              const baseColor = (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]);
              // Use a lighter/striped version for subcon tasks or a distinct color scheme
              return baseColor ? `${baseColor}80` : '#888888'; // Add transparency or use grey
            }
            return (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]) || '#cccccc';
          })
        },
        text: sortedTasks.map(task => {
          const resourceType = task.Resource === 'Subcon' ? '(Subcontractor)' : '(Machine)';
          const tooltipParts = [
            `<b>${task.Task}</b>`,
            `<b>Start:</b> ${formatDateTime(task.Start)}`,
            `<b>End:</b> ${formatDateTime(task.Finish)}`,
            `<b>Duration:</b> ${((new Date(task.Finish).getTime() - new Date(task.Start).getTime()) / (1000 * 3600)).toFixed(1)} hours`,
            `<b>Resource:</b> ${task.Resource} ${resourceType}`,
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
            // For subcontractor tasks, use a distinct pattern by modifying the color
            if (task.Resource === 'Subcon') {
              const baseColor = (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]);
              // Use a lighter/striped version for subcon tasks or a distinct color scheme
              return baseColor ? `${baseColor}80` : '#888888'; // Add transparency or use grey
            }
            return (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]) || '#cccccc';
          })
        },
      text: filteredTasks.map(task => {
        const resourceType = task.Resource === 'Subcon' ? '(Subcontractor)' : '(Machine)';
        const tooltipParts = [
          `<b>${task.Task}</b>`,
          `<b>Start:</b> ${formatDateTime(task.Start)}`,
          `<b>End:</b> ${formatDateTime(task.Finish)}`,
          `<b>Duration:</b> ${((new Date(task.Finish).getTime() - new Date(task.Start).getTime()) / (1000 * 3600)).toFixed(1)} hours`,
          `<b>Resource:</b> ${task.Resource} ${resourceType}`,
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
    title: { text: chartTitle },
    height: Math.max(700, tasks.length * 30 + 150), // Dynamic height based on number of tasks
    width: window.innerWidth * 0.95, // Responsive width
    xaxis: {
      type: 'date' as const,
      title: { text: 'Timeline (MYT)' },
      gridcolor: 'rgb(230, 230, 230)',
      gridwidth: 1,
      tickformat: '%b %d',
      dtick: 86400000,
      tickangle: -45,
      automargin: true,
      // Force timezone to be consistent with backend (Kuala Lumpur)
      timezone: 'Asia/Kuala_Lumpur',
    },
    yaxis: {
      title: { text: 'Jobs' },
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
            dtick: 3600000, // 1-hour intervals (every hour)
            timezone: 'Asia/Kuala_Lumpur',
          };
        } else {
          xAxisConfig = {
            ...layout.xaxis,
            range: xAxisRange,
            tickformat: '%b %d', // Show dates like "May 30"
            dtick: 86400000, // Daily intervals
            timezone: 'Asia/Kuala_Lumpur',
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
    if (['1d', '2d', '3d', '4d', '5d'].includes(timeRange)) {
      // For short timeframes, show hours from 01:00 to 23:59
      xAxisConfig = {
        ...layout.xaxis,
        range: xAxisRange,
        tickformat: '%H:%M', // Show hours like "08:00"
        dtick: 3600000, // 1-hour intervals (every hour)
        timezone: 'Asia/Kuala_Lumpur',
      };
    } else {
      // For longer timeframes, show dates
      xAxisConfig = {
        ...layout.xaxis,
        range: xAxisRange,
        tickformat: '%b %d', // Show dates like "May 30"
        dtick: 86400000, // Daily intervals
        timezone: 'Asia/Kuala_Lumpur',
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
      
      {!isLoading && !error && tasks.length === 0 && (
        <div className="text-center p-4">
          <h3>No Data Available</h3>
          <p>Click the "Refresh Data" button above to load schedule data.</p>
          <p><small>Data will be shared across all pages once loaded.</small></p>
        </div>
      )}
      
      {!isLoading && !error && tasks.length > 0 && (
        <Plot
          data={getTimeFilteredData() as any}
          layout={adjustedLayout as any}
          config={{ responsive: true }}
        />
      )}
    </div>
  );
};

export default GanttChartDisplay; 