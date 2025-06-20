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
  const [timeRange, setTimeRange] = useState<string>('5d');

  // Use cached data instead of local state
  const tasks: TaskData[] = data.ganttResourceView;
  const isLoading = data.isLoading;
  const error = data.error;
  const overview = data.scheduleOverview;
  
  // DEBUG: Log what data we're actually receiving
  // Only log component state once when data loads
  useEffect(() => {
    if (!isLoading && tasks.length > 0) {
      console.log('✅ [ResourceChart] Component ready with', tasks.length, 'tasks');
    }
  }, [isLoading, tasks.length]);



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

  // Helper function to extract base job ID (remove _seg suffix)
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
  const generateJobGapShapes = (mergedJobs: MergedJobData[], resourceGroups: string[]): any[] => {
    const shapes: any[] = [];
    
    mergedJobs.forEach((job, jobIndex) => {
      const resourceName = job.originalTask.Resource;
      const yPosition = resourceGroups.indexOf(resourceName);
      if (yPosition === -1) return;
      
      // Create shapes for gap periods (breaks/non-working time)
      job.gapPeriods.forEach((gap, gapIndex) => {
        const gapDurationHours = (gap.end - gap.start) / (1000 * 60 * 60);
        const gapCenterX = new Date((gap.start + gap.end) / 2);
        const gapCenterXLocal = new Date(gapCenterX.getTime() - (gapCenterX.getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
        
        // Main gap rectangle with enhanced visibility
        shapes.push({
          type: 'rect',
          xref: 'x',
          yref: 'y',
          x0: new Date(new Date(gap.start).getTime() - (new Date(gap.start).getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
          x1: new Date(new Date(gap.end).getTime() - (new Date(gap.end).getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
          y0: yPosition - 0.45,
          y1: yPosition + 0.45,
          fillcolor: 'rgba(255, 240, 240, 0.9)', // Light pink background for better visibility
          line: {
            color: '#ff4444', // Bright red border
            width: 3, // Thicker border
            dash: 'dashdot' // More prominent dash pattern
          },
          layer: 'above'
        });
        
        // Add diagonal stripes pattern for gaps > 30 minutes
        if (gapDurationHours >= 0.5) {
          // Add diagonal line pattern across the gap
          const x0 = new Date(new Date(gap.start).getTime() - (new Date(gap.start).getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
          const x1 = new Date(new Date(gap.end).getTime() - (new Date(gap.end).getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
          
          // Add multiple diagonal lines for stripe effect
          for (let i = 0; i < 3; i++) {
            shapes.push({
              type: 'line',
              xref: 'x',
              yref: 'y',
              x0: x0,
              x1: x1,
              y0: yPosition - 0.3 + (i * 0.3),
              y1: yPosition + 0.3 - (i * 0.3),
              line: {
                color: 'rgba(255, 0, 0, 0.6)',
                width: 2,
                dash: 'solid'
              },
              layer: 'above'
            });
          }
        }
        
        // Add prominent circle indicator for gaps >= 1 hour
        if (gapDurationHours >= 1) {
          shapes.push({
            type: 'circle',
            xref: 'x',
            yref: 'y',
            x0: gapCenterXLocal,
            x1: gapCenterXLocal,
            y0: yPosition - 0.15,
            y1: yPosition + 0.15,
            fillcolor: 'rgba(255, 0, 0, 0.9)', // Bright red fill
            line: { color: 'rgba(150, 0, 0, 1)', width: 3 }, // Dark red border
            layer: 'above'
          });
        }
        
        // Add small triangle indicators for shorter gaps (15min - 1hr)
        else if (gapDurationHours >= 0.25) {
          // Create triangle shape using path
          const triangleSize = 0.08;
          shapes.push({
            type: 'path',
            path: `M ${gapCenterXLocal} ${yPosition - triangleSize} L ${gapCenterXLocal} ${yPosition + triangleSize} L ${gapCenterXLocal} ${yPosition} Z`,
            xref: 'x',
            yref: 'y',
            fillcolor: 'rgba(255, 100, 0, 0.9)', // Orange fill
            line: { color: 'rgba(200, 80, 0, 1)', width: 2 },
            layer: 'above'
          });
        }
        
        // Add text label for significant gaps (> 2 hours)
        if (gapDurationHours >= 2) {
          shapes.push({
            type: 'text',
            xref: 'x',
            yref: 'y',
            x: gapCenterXLocal,
            y: yPosition + 0.2,
            text: `${gapDurationHours.toFixed(1)}h`,
            font: { 
              color: 'rgba(150, 0, 0, 1)', 
              size: 10, 
              family: 'Arial Black'
            },
            layer: 'above',
            showarrow: false
          });
        }
      });
    });
    
    return shapes;
  };

  // No automatic data loading - user must click refresh button
  
  // Log data when available (debounced to prevent spam)
  useEffect(() => {
    if (tasks.length > 0) {
      const dataLogKey = `resource-data-${tasks.length}`;
      if ((window as any).lastResourceDataLog !== dataLogKey) {
        console.log('📊 [ResourceChart] Using cached data:', tasks.length, 'tasks');
        (window as any).lastResourceDataLog = dataLogKey;
        
        // Calculate date range from the cached data
        const dates = tasks.flatMap(task => [
          new Date(task.Start),
          new Date(task.Finish)
        ]).filter(date => !isNaN(date.getTime()));
        
        if (dates.length > 0) {
          const minDate = new Date(Math.min(...dates.map(d => d.getTime())));
          let maxDate = new Date(Math.max(...dates.map(d => d.getTime())));
          
          console.log('📅 [ResourceChart] Data spans', Math.round((maxDate.getTime() - minDate.getTime()) / (1000 * 60 * 60 * 24)), 'days');
        }
      }
    } else if (!isLoading) {
      const noDataLogKey = 'resource-no-data';
      if ((window as any).lastResourceNoDataLog !== noDataLogKey) {
        console.warn('⚠️ [ResourceChart] No cached data available');
        (window as any).lastResourceNoDataLog = noDataLogKey;
      }
    }
  }, [tasks, isLoading]);



  // Filter out subcontractor tasks and create merged jobs
  const machineOnlyTasks = tasks.filter(task => task.Resource !== 'Subcontractor Work' && task.Resource !== 'Subcon');
  
  // Create merged jobs from machine tasks
  const mergedJobs = createMergedJobBarsWithGaps(machineOnlyTasks);
  
  // Debounce merged jobs logging to reduce console spam
  const jobsLogKey = `merged-jobs-${mergedJobs.length}-${machineOnlyTasks.length}`;
  if ((window as any).lastMergedJobsLogs?.[jobsLogKey] !== true) {
    console.log('📊 [ResourceChart] Created', mergedJobs.length, 'merged machine jobs');
    if (!(window as any).lastMergedJobsLogs) (window as any).lastMergedJobsLogs = {};
    (window as any).lastMergedJobsLogs[jobsLogKey] = true;
  }

  // Simple alphabetical sorting for machine resources only
  const sortMachineResources = (resources: string[]): string[] => {
    return resources.sort((a, b) => a.localeCompare(b));
  };

  const resourceGroups = sortMachineResources([...new Set(mergedJobs.map(job => job.originalTask.Resource))]);
  
  // console.log('[ResourceChart] Resource groups:', resourceGroups);
  
  // Buffer status color mapping
  const bufferStatusColors: Record<string, string> = {
    'Late': '#f44336',      // Red
    'Warning': '#ff9800',   // Orange
    'Caution': '#9c27b0',   // Purple
    'OK': '#7FFF00'         // Bright lime green
  };
  
  const plotData: Partial<PlotData>[] = [];
  
  resourceGroups.forEach(resource => {
    const resourceJobs = mergedJobs.filter(job => job.originalTask.Resource === resource);
    
    // console.log(`[ResourceChart] Resource ${resource}: ${resourceJobs.length} merged jobs`);
    
    // Create timeline visualization using scatter plots instead of problematic bar charts
    resourceJobs.forEach((job, jobIndex) => {
      const task = job.originalTask;
      
      // Get color for this job
      const jobColor = (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]) || '#cccccc';
      
      // Create tooltip text
      const workDuration = job.segments.reduce((total, seg) => total + (seg.end - seg.start), 0) / (1000 * 3600);
      const totalDuration = job.totalDuration / (1000 * 3600);
      const gapDuration = totalDuration - workDuration;

      const tooltipParts = [
        `<b>${job.baseJobId}</b> <i>(Consolidated View)</i>${task.JobFamily ? ` (${task.JobFamily})` : ''}`,
        `<b>Machine:</b> ${task.Resource}`,
        `<b>Overall Start:</b> ${formatDateTime(new Date(job.overallStartTime).toISOString())}`,
        `<b>Overall End:</b> ${formatDateTime(new Date(job.overallEndTime).toISOString())}`,
        `<b>Work Duration:</b> ${workDuration.toFixed(1)} hours`,
        `<b>Total Duration:</b> ${totalDuration.toFixed(1)} hours`
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

      tooltipParts.push(`<b>Priority:</b> ${task.PriorityLabel || 'Unknown'}`);
      
      const tooltipText = tooltipParts.join('<br>');
      
      // Create work segments as thick lines
      job.segments.forEach((segment, segIndex) => {
        // Convert timestamps to local timezone without timezone offset
        const startTime = new Date(segment.start);
        const endTime = new Date(segment.end);
        
        // Format as local time without timezone offset for Plotly
        const startLocal = new Date(startTime.getTime() - (startTime.getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
        const endLocal = new Date(endTime.getTime() - (endTime.getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
        
        plotData.push({
          type: 'scatter',
          mode: 'lines',
          x: [startLocal, endLocal],
          y: [resource, resource],
          line: {
            color: jobColor,
            width: 20
          },
          text: [tooltipText, tooltipText],
          hoverinfo: 'text',
          showlegend: false,
          name: `${job.baseJobId}_work_${segIndex}`
        } as any);
      });
      
      // Gap periods are shown as empty space between work segments
      // No visual gap indicators needed - clean timeline view
    });
  });

  // console.log('[ResourceChart] Generated plotData:', plotData.length, 'series');
  // console.log('[ResourceChart] Sample plotData entry:', plotData[0]);
  
  // Debug the actual chart data values
  if (plotData.length > 0 && plotData[0]) {
    // console.log('[ResourceChart] First series x values (durations):', plotData[0].x);
    // console.log('[ResourceChart] First series y values (resources):', plotData[0].y);
    // console.log('[ResourceChart] First series base values (start times):', (plotData[0] as any).base);
  }

  const chartTitle = title || 'Production Planning System (by Resource)';
  
  const handleTimeRangeChange = (range: string) => {
    // console.log('[ResourceChart] Time range changing from', timeRange, 'to', range);
    if (range !== timeRange) {
      setTimeRange(range);
      // console.log('[ResourceChart] Time range state updated to:', range);
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
    // console.log('[ResourceChart] getTimeFilteredData called with timeRange:', timeRange);
    
    // If timeframe is 'all' or we have no merged jobs, return scatter plot data
    if (timeRange === 'all' || mergedJobs.length === 0) {
      // console.log('[ResourceChart] Using all merged jobs for "all" timeframe:', mergedJobs.length);
      // console.log('[ResourceChart] Returning plotData with', plotData.length, 'series');
      return plotData; // Return the scatter plot data
    }
    
    const now = new Date();
    // console.log('[ResourceChart] Current timeRange:', timeRange);
    // console.log('[ResourceChart] Total merged jobs before filtering:', mergedJobs.length);
    
    // Find earliest and latest dates in the merged jobs dataset
    const validDates = mergedJobs
      .map(job => [new Date(job.overallStartTime), new Date(job.overallEndTime)])
      .filter(([start, end]) => !isNaN(start.getTime()) && !isNaN(end.getTime()));
    
    if (validDates.length === 0) {
      console.error('[ResourceChart] No valid dates found in merged job data');
      return [];
    }
    
    // Find earliest date in dataset
    const allTimestamps = validDates.flatMap(([start, end]) => [start.getTime(), end.getTime()]);
    const earliestDate = new Date(Math.min(...allTimestamps));
    const latestDate = new Date(Math.max(...allTimestamps));
    
    // console.log('[ResourceChart] Dataset date range:', {
    //   earliest: earliestDate.toISOString(),
    //   latest: latestDate.toISOString(),
    //   span: Math.round((latestDate.getTime() - earliestDate.getTime()) / (1000 * 60 * 60 * 24)) + ' days'
    // });
    
    // Always filter forward from today's date for time range selections
    // Set startDate to beginning of today (00:00:00) to capture jobs that started earlier today
    let startDate = new Date(now);
    startDate.setHours(0, 0, 0, 0); // Start from beginning of today
    let endDate = new Date(now);
    
    // console.log('[ResourceChart] Filtering forward from today for timeRange:', timeRange);
    
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
    
    // console.log('[ResourceChart] Filter date range:', {
    //   start: startDate.toISOString(),
    //   end: endDate.toISOString()
    // });
    
    // Filter merged jobs to include anything that falls within our date range
    const startTimestamp = startDate.getTime();
    const endTimestamp = endDate.getTime();
    
    const filteredJobs = mergedJobs.filter(job => {
      // A job should be included if:
      // 1. It starts within our date range, OR
      // 2. It ends within our date range, OR
      // 3. It spans our date range (starts before and ends after)
      return (job.overallStartTime >= startTimestamp && job.overallStartTime <= endTimestamp) ||
             (job.overallEndTime >= startTimestamp && job.overallEndTime <= endTimestamp) ||
             (job.overallStartTime <= startTimestamp && job.overallEndTime >= endTimestamp);
    });
    
    // Only log significant filter changes (debounce duplicates)
    if (filteredJobs.length < mergedJobs.length) {
      const logKey = `resource-filter-${timeRange}-${filteredJobs.length}-${mergedJobs.length}`;
      if ((window as any).lastResourceFilterLogs?.[logKey] !== true) {
        console.log('🔍 [ResourceChart] Filtered to', filteredJobs.length, 'of', mergedJobs.length, 'jobs for', timeRange);
        if (!(window as any).lastResourceFilterLogs) (window as any).lastResourceFilterLogs = {};
        (window as any).lastResourceFilterLogs[logKey] = true;
      }
    }
    
    // If no jobs matched, show an empty chart rather than erroring
    if (filteredJobs.length === 0) {
      console.warn('[ResourceChart] No merged jobs passed the time filter for:', timeRange);
      return [];
    }
    
    // Create filtered plotData using bar charts (like GanttChartDisplay)
    const filteredPlotData: Partial<PlotData>[] = [];
    
    // Get unique resources from filtered jobs
    const filteredResourceGroups = sortMachineResources([...new Set(filteredJobs.map(job => job.originalTask.Resource))]);
    
    // Create one bar trace per resource
    filteredResourceGroups.forEach(resource => {
      const resourceJobs = filteredJobs.filter(job => job.originalTask.Resource === resource);
      
      if (resourceJobs.length === 0) return;
      
      filteredPlotData.push({
        type: 'bar',
        orientation: 'h',
        x: resourceJobs.map(job => job.totalDuration), // Total duration including gaps
        y: resourceJobs.map(() => resource), // All jobs for this resource on same y-position
        base: resourceJobs.map(job => {
          // Convert timestamp to local time format for Plotly
          const startDate = new Date(job.overallStartTime);
          const localISOString = new Date(startDate.getTime() - (startDate.getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
          return localISOString;
        }),
        marker: {
          color: resourceJobs.map(job => {
            const task = job.originalTask;
            return (task.BufferStatusLabel && bufferStatusColors[task.BufferStatusLabel]) || '#cccccc';
          })
        },
        text: resourceJobs.map(job => {
          const task = job.originalTask;
          const workDuration = job.segments.reduce((total, seg) => total + (seg.end - seg.start), 0) / (1000 * 3600);
          const totalDuration = job.totalDuration / (1000 * 3600);
          const gapDuration = totalDuration - workDuration;

          const tooltipParts = [
            `<b>${job.baseJobId}</b> <i>(Consolidated View)</i>${task.JobFamily ? ` (${task.JobFamily})` : ''}`,
            `<b>Machine:</b> ${task.Resource}`,
            `<b>Overall Start:</b> ${formatDateTime(new Date(job.overallStartTime).toISOString())}`,
            `<b>Overall End:</b> ${formatDateTime(new Date(job.overallEndTime).toISOString())}`,
            `<b>Work Duration:</b> ${workDuration.toFixed(1)} hours`,
            `<b>Total Duration:</b> ${totalDuration.toFixed(1)} hours`
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

          tooltipParts.push(`<b>Priority:</b> ${task.PriorityLabel || 'Unknown'}`);
          
          return tooltipParts.join('<br>');
        }),
        hoverinfo: 'text',
        showlegend: false,
        name: resource
      } as any);
    });
    
    // Debounce trace generation log
    const traceLogKey = `resource-traces-${timeRange}-${filteredPlotData.length}-${filteredJobs.length}`;
    if ((window as any).lastResourceTraceLogs?.[traceLogKey] !== true) {
      console.log('🎯 [ResourceChart] Generated', filteredPlotData.length, 'bar traces for', timeRange);
      if (!(window as any).lastResourceTraceLogs) (window as any).lastResourceTraceLogs = {};
      (window as any).lastResourceTraceLogs[traceLogKey] = true;
    }
    return filteredPlotData;
  };

  const layout = {
    title: chartTitle,
    height: Math.max(700, resourceGroups.length * 50 + 200), // Adjusted height for resource groups
    width: window.innerWidth * 0.95,
    xaxis: {
      type: 'date' as const,
      title: 'Timeline (MYT)',
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
    shapes: [
      // Add gap shapes for merged jobs
      ...generateJobGapShapes(mergedJobs, resourceGroups),
      // Current time line
      {
        type: 'line',
        x0: new Date(new Date().getTime() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
        y0: -0.5,
        x1: new Date(new Date().getTime() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
        y1: resourceGroups.length - 0.5,
        line: {
          color: 'red',
          width: 2,
          dash: 'dash'
        }
      }
    ]
  };

  // Calculate layout based on filtered merged jobs
  const calculateFilteredLayout = () => {
    // For "all" timeframe, we can just use all merged jobs
    if (timeRange === 'all') {
      // Get all unique resources for the y-axis
      const allResourceGroups = sortMachineResources([...new Set(mergedJobs.map(job => job.originalTask.Resource))]);
      
      // Calculate the actual data range for 'all' timeframe
      const allValidDates = mergedJobs
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
        height: Math.max(700, allResourceGroups.length * 50 + 200),
        xaxis: xAxisConfig,
        yaxis: {
          ...layout.yaxis,
          type: 'category',
          categoryorder: 'array' as const,
                  categoryarray: sortMachineResources([...allResourceGroups]),
          autorange: 'reversed' as const,
        },
        shapes: [
          // Add gap shapes for merged jobs
          ...generateJobGapShapes(mergedJobs, allResourceGroups),
          // Current time line
          {
            type: 'line',
            x0: new Date(new Date().getTime() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
            y0: -0.5,
            x1: new Date(new Date().getTime() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
            y1: allResourceGroups.length - 0.5,
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
    
    // Find earliest and latest dates in the dataset
    const validDates = machineOnlyTasks
      .map(task => [parseDateSafely(task.Start), parseDateSafely(task.Finish)])
      .filter(([start, end]) => start !== null && end !== null) as [Date, Date][];
      
    if (validDates.length === 0) {
      return {
        ...layout,
        height: 700,
        shapes: [
          // Add gap shapes even for empty state to maintain consistency
          ...generateJobGapShapes(mergedJobs, resourceGroups),
          // Current time line
          {
            type: 'line',
            x0: new Date(new Date().getTime() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
            y0: -0.5,
            x1: new Date(new Date().getTime() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
            y1: resourceGroups.length - 0.5,
            line: {
              color: 'red',
              width: 2,
              dash: 'dash'
            }
          }
        ]
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
    
    const filteredTasksForLayout = machineOnlyTasks.filter(task => {
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
    // Convert to local time format for Plotly (without Z suffix)
    const startDateLocal = new Date(startDate.getTime() - (startDate.getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
    const endDateLocal = new Date(endDate.getTime() - (endDate.getTimezoneOffset() * 60000)).toISOString().slice(0, -1);
    const xAxisRange = [startDateLocal, endDateLocal];
    
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
      height: Math.max(700, filteredResourceGroups.length * 50 + 200),
      xaxis: xAxisConfig,
      yaxis: {
        ...layout.yaxis,
        type: 'category',
        categoryorder: 'array' as const,
        categoryarray: sortMachineResources([...filteredResourceGroups]),
        autorange: 'reversed' as const,
      },
      shapes: [
        // Add gap shapes for filtered jobs
        ...generateJobGapShapes(
          mergedJobs.filter(job => filteredResourceGroups.includes(job.originalTask.Resource)),
          filteredResourceGroups
        ),
        // Current time line
        {
          type: 'line',
          x0: new Date(new Date().getTime() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
          y0: -0.5,
          x1: new Date(new Date().getTime() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, -1),
          y1: filteredResourceGroups.length - 0.5,
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
          layout={{
            ...adjustedLayout,
            hovermode: 'x unified',
            hoverlabel: {
              bgcolor: 'white',
              bordercolor: 'lightgray',
              font: { size: 13 }
            },
            xaxis: {
              ...adjustedLayout.xaxis,
              showspikes: true,
              spikemode: 'across',
              spikesnap: 'cursor',
              showline: false,
              showgrid: true,
              spikecolor: 'grey',
              spikethickness: 1,
              spikedash: 'dash'
            },
            yaxis: {
              ...adjustedLayout.yaxis,
              showspikes: true,
              spikemode: 'across',
              spikesnap: 'cursor',
              showline: false,
              showgrid: true,
              spikecolor: 'grey',
              spikethickness: 1,
              spikedash: 'dash'
            }
          } as any}
          config={{ 
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
          }}
        />
      )}
    </div>
  );
};

export default ResourceChart;
