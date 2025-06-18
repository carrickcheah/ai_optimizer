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

// Helper function to extract base job ID from segmented task names
const getBaseJobId = (taskId: string): string => {
  // Remove _seg suffix if present (e.g., "JOB123-P1_seg0" -> "JOB123-P1")
  const segIndex = taskId.lastIndexOf('_seg');
  if (segIndex !== -1) {
    return taskId.substring(0, segIndex);
  }
  return taskId;
};

// Interface for merged job data
interface MergedJobData {
  baseJobId: string;
  overallStartTime: number;
  overallEndTime: number;
  totalDuration: number;
  segments: Array<{
    start: number;
    end: number;
    startIso: string;
    endIso: string;
  }>;
  gapPeriods: Array<{
    start: number;
    end: number;
  }>;
  originalTask: any; // Keep reference to original task data
}

// Helper function to create merged job bars with gap information
const createMergedJobBarsWithGaps = (tasks: any[]): MergedJobData[] => {
  if (!tasks || tasks.length === 0) {
    return [];
  }

  // Group tasks by base job ID
  const jobGroups: Record<string, any[]> = {};
  
  tasks.forEach(task => {
    const baseJobId = getBaseJobId(task.Task);
    if (!jobGroups[baseJobId]) {
      jobGroups[baseJobId] = [];
    }
    jobGroups[baseJobId].push(task);
  });

  // Create merged job data for each group
  const mergedJobs: MergedJobData[] = [];
  
  Object.entries(jobGroups).forEach(([baseJobId, jobTasks]) => {
    // Sort segments by start time
    const sortedTasks = jobTasks.sort((a, b) => 
      new Date(a.Start).getTime() - new Date(b.Start).getTime()
    );
    
    const segments = sortedTasks.map(task => ({
      start: new Date(task.Start).getTime(),
      end: new Date(task.Finish).getTime(),
      startIso: task.Start,
      endIso: task.Finish
    }));
    
    const overallStartTime = Math.min(...segments.map(s => s.start));
    const overallEndTime = Math.max(...segments.map(s => s.end));
    const totalDuration = overallEndTime - overallStartTime;
    
    // Calculate gap periods between segments
    const gapPeriods: Array<{ start: number; end: number }> = [];
    for (let i = 0; i < segments.length - 1; i++) {
      const currentEnd = segments[i].end;
      const nextStart = segments[i + 1].start;
      
      // If there's a gap between segments, record it
      if (nextStart > currentEnd) {
        gapPeriods.push({
          start: currentEnd,
          end: nextStart
        });
      }
    }
    
    mergedJobs.push({
      baseJobId,
      overallStartTime,
      overallEndTime,
      totalDuration,
      segments,
      gapPeriods,
      originalTask: sortedTasks[0] // Use first segment for original task data
    });
  });
  
  return mergedJobs;
};

// Helper function to generate Plotly shapes for job gaps
const generateJobGapShapes = (mergedJobs: MergedJobData[], yAxisLabels: string[]): any[] => {
  const shapes: any[] = [];
  
  mergedJobs.forEach((job, jobIndex) => {
    const yPosition = yAxisLabels.indexOf(job.baseJobId);
    if (yPosition === -1) return;
    
    // Create shapes for gap periods (breaks/non-working time)
    job.gapPeriods.forEach(gap => {
      shapes.push({
        type: 'rect',
        xref: 'x',
        yref: 'y',
        x0: new Date(new Date(gap.start).getTime() - (new Date(gap.start).getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
        x1: new Date(new Date(gap.end).getTime() - (new Date(gap.end).getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
        y0: yPosition - 0.45,
        y1: yPosition + 0.45,
        fillcolor: 'rgba(255, 255, 255, 0.95)', // More opaque white background for gaps
        line: {
          color: 'rgba(150, 150, 150, 1.0)',
          width: 2,
          dash: 'dash'
        },
        layer: 'above'
      });
    });
  });
  
  return shapes;
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
  const { data, clearCache, refreshData } = useDataCache();
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
  
  // Create segmented tasks for gap analysis, then merge them back
  const segmentedTasks = tasks.flatMap(task => {
    const duration = new Date(task.Finish).getTime() - new Date(task.Start).getTime();
    const hoursDuration = duration / (1000 * 60 * 60);
    
    // Only segment tasks longer than 4 hours (likely to span breaks)
    if (hoursDuration > 4) {
      return createTaskSegmentsWithBreaks(task);
    }
    return [task];
  });
  
  // Create merged job bars with gap information
  const mergedJobsWithGaps = createMergedJobBarsWithGaps(segmentedTasks);
  
  // Sort merged jobs by job ID for consistency
  const sortedMergedJobs = [...mergedJobsWithGaps].sort((a, b) => {
    const partsA = getTaskParts(a.baseJobId);
    const partsB = getTaskParts(b.baseJobId);

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
  
  // For backward compatibility, also keep the segmented tasks sorted (some functions may still need this)
  const sortedTasks = [...segmentedTasks].sort((a, b) => {
    const partsA = getTaskParts(a.Task);
    const partsB = getTaskParts(b.Task);

    const jobCompare = partsA.jobGroup.localeCompare(partsB.jobGroup);
    if (jobCompare !== 0) {
      return jobCompare;
    }

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
    // Use merged jobs for all timeframes to show consolidated view
    if (timeRange === 'all' || sortedMergedJobs.length === 0) {
      console.log('Using all merged jobs for "all" timeframe:', sortedMergedJobs.length);
      
      // Create timeline visualization using scatter plots instead of problematic bar charts
      const timelineTraces: any[] = [];
      
      sortedMergedJobs.forEach((job, jobIndex) => {
        const task = job.originalTask;
        const yPosition = jobIndex;
        
        // Get color for this job
        let jobColor;
        if (task.Resource === 'Subcon') {
          const baseColor = (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]);
          jobColor = baseColor ? `${baseColor}80` : '#888888';
        } else {
          jobColor = (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]) || '#cccccc';
        }
        
        // Create tooltip text
        const resourceType = task.Resource === 'Subcon' ? '(Subcontractor)' : '(Machine)';
        const workDuration = job.segments.reduce((total, seg) => total + (seg.end - seg.start), 0) / (1000 * 3600);
        const totalDuration = job.totalDuration / (1000 * 3600);
        const gapDuration = totalDuration - workDuration;
        
        const tooltipParts = [
          `<b>${job.baseJobId}</b> <i>(Consolidated View)</i>`,
          `<b>Overall Start:</b> ${formatDateTime(new Date(job.overallStartTime).toISOString())}`,
          `<b>Overall End:</b> ${formatDateTime(new Date(job.overallEndTime).toISOString())}`,
          `<b>Work Duration:</b> ${workDuration.toFixed(1)} hours`,
          `<b>Total Duration:</b> ${totalDuration.toFixed(1)} hours`,
        ];
        
        if (gapDuration > 0) {
          tooltipParts.push(`<b>Break Time:</b> ${gapDuration.toFixed(1)} hours (${((gapDuration/totalDuration)*100).toFixed(1)}%)`);
        }
        
        if (job.segments.length > 1) {
          tooltipParts.push(`<b>Work Periods:</b> ${job.segments.length} segments with gaps between`);
          tooltipParts.push(`<b>Break Gaps:</b> ${job.gapPeriods.length} break periods (shown as empty space)`);
        } else {
          tooltipParts.push(`<b>Work Periods:</b> Single continuous work period`);
        }
        
        tooltipParts.push(
          `<b>Resource:</b> ${task.Resource} ${resourceType}`,
          `<b>Priority:</b> ${task.PriorityLabel || 'Unknown'}`
        );
        
        if (task.JobFamily) {
          tooltipParts.push(`<b>Job Family:</b> ${task.JobFamily}`);
        }
        
        const tooltipText = tooltipParts.join('<br>');
        
        // Create work segments as thick lines
        job.segments.forEach((segment, segIndex) => {
          // Convert timestamps to local timezone without timezone offset
          const startTime = new Date(segment.start);
          const endTime = new Date(segment.end);
          
          // Format as local time without timezone offset for Plotly
          const startLocal = new Date(startTime.getTime() - (startTime.getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
          const endLocal = new Date(endTime.getTime() - (endTime.getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
          
          timelineTraces.push({
            type: 'scatter',
            mode: 'lines',
            x: [startLocal, endLocal],
            y: [job.baseJobId, job.baseJobId],
            line: {
              color: jobColor,
              width: 20
            },
            text: [tooltipText, tooltipText],
            hoverinfo: 'text',
            showlegend: false,
            name: `${job.baseJobId}_work_${segIndex}`
          });
        });
        
        // Gap periods are shown as empty space between work segments
        // No visual gap indicators needed - clean timeline view
      });
      
      return timelineTraces;
    }
    
    const now = new Date();
    console.log('Current timeRange:', timeRange);
    console.log('Total merged jobs before filtering:', sortedMergedJobs.length);
    
    // Find earliest and latest dates in the merged jobs dataset
    const validDates = sortedMergedJobs
      .map(job => [new Date(job.overallStartTime), new Date(job.overallEndTime)])
      .filter(([start, end]) => !isNaN(start.getTime()) && !isNaN(end.getTime()));
    
    if (validDates.length === 0) {
      console.error('No valid dates found in merged job data');
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
    
    // Filter merged jobs to include anything that falls within our date range
    const startTimestamp = startDate.getTime();
    const endTimestamp = endDate.getTime();
    
    const filteredJobs = sortedMergedJobs.filter(job => {
      // A job should be included if:
      // 1. It starts within our date range, OR
      // 2. It ends within our date range, OR
      // 3. It spans our date range (starts before and ends after)
      return (job.overallStartTime >= startTimestamp && job.overallStartTime <= endTimestamp) ||
             (job.overallEndTime >= startTimestamp && job.overallEndTime <= endTimestamp) ||
             (job.overallStartTime <= startTimestamp && job.overallEndTime >= endTimestamp);
    });
    
    console.log('Filtered merged jobs for', timeRange, ':', filteredJobs.length, 'of', sortedMergedJobs.length);
    
    // If no jobs matched, show an empty chart rather than erroring
    if (filteredJobs.length === 0) {
      console.warn('No merged jobs passed the time filter for:', timeRange);
      return [];
    }
    
    return [{
      type: 'bar',
      x: filteredJobs.map(job => job.totalDuration), // Total duration including gaps
      y: filteredJobs.map(job => job.baseJobId),
      base: filteredJobs.map(job => new Date(job.overallStartTime).toISOString()),
      orientation: 'h',
      marker: {
        color: filteredJobs.map(job => {
          const task = job.originalTask;
          // For subcontractor tasks, use a distinct pattern by modifying the color
          if (task.Resource === 'Subcon') {
            const baseColor = (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]);
            // Use a lighter/striped version for subcon tasks or a distinct color scheme
            return baseColor ? `${baseColor}80` : '#888888'; // Add transparency or use grey
          }
          return (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]) || '#cccccc';
        })
      },
      text: filteredJobs.map(job => {
        const task = job.originalTask;
        const resourceType = task.Resource === 'Subcon' ? '(Subcontractor)' : '(Machine)';
        const workDuration = job.segments.reduce((total, seg) => total + (seg.end - seg.start), 0) / (1000 * 3600);
        const totalDuration = job.totalDuration / (1000 * 3600);
        const gapDuration = totalDuration - workDuration;
        
        const tooltipParts = [
          `<b>${job.baseJobId}</b> <i>(Consolidated View)</i>`,
          `<b>Overall Start:</b> ${formatDateTime(new Date(job.overallStartTime).toISOString())}`,
          `<b>Overall End:</b> ${formatDateTime(new Date(job.overallEndTime).toISOString())}`,
          `<b>Work Duration:</b> ${workDuration.toFixed(1)} hours`,
          `<b>Total Duration:</b> ${totalDuration.toFixed(1)} hours`,
        ];
        
        if (gapDuration > 0) {
          tooltipParts.push(`<b>Break Time:</b> ${gapDuration.toFixed(1)} hours (${((gapDuration/totalDuration)*100).toFixed(1)}%)`);
        }
        
        if (job.segments.length > 1) {
          tooltipParts.push(`<b>Work Periods:</b> ${job.segments.length} segments merged into single bar`);
          tooltipParts.push(`<b>Gaps Shown:</b> ${job.gapPeriods.length} break periods as white dashed areas`);
        } else {
          tooltipParts.push(`<b>Work Periods:</b> Single continuous work period`);
        }
        
        tooltipParts.push(
          `<b>Resource:</b> ${task.Resource} ${resourceType}`,
          `<b>Priority:</b> ${task.PriorityLabel || 'Unknown'}`
        );
        
        if (task.JobFamily) {
          tooltipParts.push(`<b>Job Family:</b> ${task.JobFamily}`);
        }
        
        return tooltipParts.join('<br>');
      }),
      hoverinfo: 'text',
      name: 'Jobs'
    }];
  };

  const layout = {
    title: { text: chartTitle },
    height: Math.max(700, sortedMergedJobs.length * 30 + 150), // Dynamic height based on number of merged jobs
    width: window.innerWidth * 0.95, // Responsive width
    xaxis: {
      type: 'date' as const,
      title: { text: 'Timeline (MYT)' },
      gridcolor: 'rgb(230, 230, 230)',
      gridwidth: 1,
      tickformat: '%b %d',
      dtick: 86400000,
      tickangle: -90,
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

  // Calculate layout based on filtered merged jobs
  const calculateFilteredLayout = () => {
    // Get current data for layout calculation
    const currentFilteredData = getTimeFilteredData();
    const currentJobLabels = currentFilteredData.length > 0 ? currentFilteredData[0].y as string[] : [];
    
    // For "all" timeframe, calculate actual data range
    if (timeRange === 'all') {
      // Calculate the actual data range for 'all' timeframe using merged jobs
      const allValidDates = sortedMergedJobs
        .map(job => [new Date(job.overallStartTime), new Date(job.overallEndTime)])
        .filter(([start, end]) => !isNaN(start.getTime()) && !isNaN(end.getTime()));
      
      let xAxisConfig;
      if (allValidDates.length > 0) {
        const allTimestamps = allValidDates.flatMap(([start, end]) => [start.getTime(), end.getTime()]);
        const minDate = new Date(Math.min(...allTimestamps));
        const maxDate = new Date(Math.max(...allTimestamps));
        
        // Format dates without timezone offset for consistent display
        const minDateLocal = new Date(minDate.getTime() - (minDate.getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
        const maxDateLocal = new Date(maxDate.getTime() - (maxDate.getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
        const xAxisRange = [minDateLocal, maxDateLocal];
        
        // Check if data spans less than 2 days, use hour format
        const timeSpanHours = (maxDate.getTime() - minDate.getTime()) / (1000 * 60 * 60);
        if (timeSpanHours <= 48) {
          xAxisConfig = {
            ...layout.xaxis,
            range: xAxisRange,
            tickformat: '%H:%M', // Show hours like "08:00"
            dtick: 3600000, // 1-hour intervals (every hour)
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
      
      // Generate gap shapes for all merged jobs
      const gapShapes = generateJobGapShapes(sortedMergedJobs, sortedMergedJobs.map(job => job.baseJobId));
      
      return {
        ...layout,
        height: Math.max(700, sortedMergedJobs.length * 30 + 150),
        xaxis: xAxisConfig,
        shapes: [
          ...gapShapes,
          {
            type: 'line',
            x0: new Date(new Date().getTime() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
            y0: -0.5,
            x1: new Date(new Date().getTime() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
            y1: sortedMergedJobs.length > 0 ? sortedMergedJobs.length - 0.5 : 10,
            line: {
              color: 'red',
              width: 2,
              dash: 'dash'
            }
          }
        ]
      };
    }
    
    const now = new Date();
    
    // Find earliest and latest dates in the merged jobs dataset
    const validDates = sortedMergedJobs
      .map(job => [new Date(job.overallStartTime), new Date(job.overallEndTime)])
      .filter(([start, end]) => !isNaN(start.getTime()) && !isNaN(end.getTime()));
      
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
    // Set startDate to beginning of today (00:00:00) to capture jobs that started earlier today
    let startDate = new Date(now);
    startDate.setHours(0, 0, 0, 0); // Start from beginning of today
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
    
    // Filter merged jobs with the same logic we use in getTimeFilteredData
    const startTimestamp = startDate.getTime();
    const endTimestamp = endDate.getTime();
    
    const filteredJobsForLayout = sortedMergedJobs.filter(job => {
      return (job.overallStartTime >= startTimestamp && job.overallStartTime <= endTimestamp) ||
             (job.overallEndTime >= startTimestamp && job.overallEndTime <= endTimestamp) ||
             (job.overallStartTime <= startTimestamp && job.overallEndTime >= endTimestamp);
    });
    
    // Ensure we have reasonable height even with few jobs
    const adjustedHeight = Math.max(700, filteredJobsForLayout.length * 30 + 150);
    
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
    
    // Generate gap shapes for filtered jobs only
    const gapShapes = generateJobGapShapes(filteredJobsForLayout, currentJobLabels);
    
    return {
      ...layout,
      height: adjustedHeight,
      xaxis: xAxisConfig,
      shapes: [
        ...gapShapes,
        {
          type: 'line',
          x0: new Date().toISOString(),
          y0: -0.5,
          x1: new Date().toISOString(),
          y1: filteredJobsForLayout.length > 0 ? filteredJobsForLayout.length - 0.5 : 10,
          line: {
            color: 'red',
            width: 2,
            dash: 'dash'
          }
        }
      ]
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
        <div style={{marginLeft: '20px'}}>
          <button 
            className="flat-inactive"
            onClick={async () => {
              clearCache();
              await refreshData();
            }}
            style={{
              backgroundColor: '#dc3545',
              color: 'white',
              border: 'none',
              padding: '8px 12px',
              borderRadius: '4px',
              fontSize: '12px',
              cursor: 'pointer'
            }}
            title="Clear cache and reload fresh data"
          >
            🗑️ Clear Cache
          </button>
        </div>
      </div>
      
      {overview && (
        <div className="overview-section">
          <div className="overview-left">
            <h3>Schedule Overview</h3>
            <div className="overview-stats">
              <div className="stat-item">
                <span className="stat-label">Total Jobs:</span>
                <span className="stat-value">{sortedMergedJobs.length}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Date Range:</span>
                <span className="stat-value">{
                  (() => {
                    if (sortedMergedJobs.length === 0) return 'N/A';
                    const dates = sortedMergedJobs.map(job => [new Date(job.overallStartTime), new Date(job.overallEndTime)]).flat();
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
                <span className="stat-label">Work Duration:</span>
                <span className="stat-value">{
                  (() => {
                    if (sortedMergedJobs.length === 0) return '0 hours';
                    const totalWorkDuration = sortedMergedJobs.reduce((total, job) => {
                      const workDuration = job.segments.reduce((segTotal, seg) => segTotal + (seg.end - seg.start), 0);
                      return total + workDuration;
                    }, 0);
                    const totalHours = Math.round(totalWorkDuration / (1000 * 60 * 60));
                    return `${totalHours.toLocaleString()} hours`;
                  })()
                }</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Records Displayed:</span>
                <span className="stat-value">{sortedMergedJobs.length}</span>
              </div>
            </div>
          </div>
          
          <div className="overview-right">
            <h3>Buffer Status</h3>
            <div className="buffer-overview">
              <div className="buffer-rows">
                {(() => {
                  // Calculate actual buffer status counts from merged jobs
                  const bufferCounts = {
                    Late: sortedMergedJobs.filter(job => job.originalTask.BufferStatusLabel === 'Late').length,
                    Warning: sortedMergedJobs.filter(job => job.originalTask.BufferStatusLabel === 'Warning').length,
                    Caution: sortedMergedJobs.filter(job => job.originalTask.BufferStatusLabel === 'Caution').length,
                    OK: sortedMergedJobs.filter(job => job.originalTask.BufferStatusLabel === 'OK').length
                  };
                  const totalJobs = sortedMergedJobs.length || 1; // Avoid division by zero
                  
                  return (
                    <>
                      <div className="buffer-row">
                        <div className="buffer-label buffer-label-late">Late</div>
                        <div className="buffer-bar-container">
                          <div 
                            className="buffer-bar-fill buffer-late" 
                            style={{ width: `${(bufferCounts.Late / totalJobs) * 100}%` }}
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
                            style={{ width: `${(bufferCounts.Warning / totalJobs) * 100}%` }}
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
                            style={{ width: `${(bufferCounts.Caution / totalJobs) * 100}%` }}
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
                            style={{ width: `${(bufferCounts.OK / totalJobs) * 100}%` }}
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
      
      {!isLoading && !error && sortedMergedJobs.length === 0 && (
        <div className="text-center p-4">
          <h3>No Data Available</h3>
          <p>Click the "Refresh Data" button above to load schedule data.</p>
          <p><small>Data will be shared across all pages once loaded.</small></p>
        </div>
      )}
      
      {!isLoading && !error && sortedMergedJobs.length > 0 && (
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