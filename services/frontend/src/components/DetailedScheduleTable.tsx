import React, { useState, useEffect, useMemo } from 'react';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { API_BASE_URL } from '../config';
import './DetailedScheduleTable.css';

// Helper function to format column headers with newlines
const formatColumnHeader = (header: any): React.ReactNode => {
  // Only process string headers that have newlines
  if (typeof header === 'string' && header.includes('\n')) {
    return header.split('\n').map((part, i) => (
      <React.Fragment key={i}>
        {part}
        {i < header.split('\n').length - 1 && <br />}
      </React.Fragment>
    ));
  }
  return header;
};

// Matches the structure from prepare_detailed_schedule_table_data in backend
interface ScheduleTableRow {
  op_id: string;
  job_id: string;
  lcd_date_str?: string;
  job?: string;
  process_code?: string;
  job_dependency?: string;
  rsc_location?: string;
  rsc_code?: string;
  number_operator?: number;
  job_quantity?: number;
  expect_output_per_hour?: number;
  priority?: number;
  hours_need?: number;
  setting_hours?: number;
  break_hours?: number;
  no_prod?: number;
  start_date_input_str?: string;
  accumulated_daily_output?: number;
  balance_quantity?: number;
  scheduled_start_time_str?: string;
  scheduled_end_time_str?: string;
  bal_hr?: number;
  buffer_status?: string;
  // Include epoch dates if you need them for client-side logic not covered by string sort
  lcd_date_epoch?: number;
}

interface ScheduleOverview {
  total_jobs: number;
  date_range: string;
  total_duration: string;
  records_displayed: number;
  buffer_status_counts: {
    Late: number;
    Warning: number;
    Caution: number;
    OK: number;
  };
}

// Helper function to format date-time strings
const formatDateTime = (dateTimeStr: string | undefined): React.ReactNode => {
  if (!dateTimeStr) return 'N/A';
  
  // Split the datetime string to get parts (assuming format like "YYYY-MM-DD HH:MM:SS")
  const parts = dateTimeStr.split(' ');
  if (parts.length !== 2) return dateTimeStr; // Return as is if not in expected format
  
  return (
    <div className="date-time-display">
      <div className="date-part">{parts[0]}</div>
      <div className="time-part">{parts[1]}</div>
    </div>
  );
};

// Helper function specifically for LCD Date format (date + HH:MM)
const formatLCDDate = (dateTimeStr: string | undefined): React.ReactNode => {
  if (!dateTimeStr) return 'N/A';
  
  // Handle different date formats from backend
  // Expected input: "20/06/25 10:00" (DD/MM/YY HH:MM)
  const parts = dateTimeStr.split(' ');
  if (parts.length !== 2) return dateTimeStr; // Return as is if not in expected format
  
  const datePart = parts[0]; // "20/06/25"
  const timePart = parts[1]; // "10:00"
  
  // Convert DD/MM/YY to YYYY-MM-DD
  const dateComponents = datePart.split('/');
  if (dateComponents.length === 3) {
    const day = dateComponents[0].padStart(2, '0');
    const month = dateComponents[1].padStart(2, '0');
    let year = dateComponents[2];
    
    // Convert YY to YYYY (assuming 20xx for years like 25 = 2025)
    if (year.length === 2) {
      year = '20' + year;
    }
    
    const formattedDate = `${year}-${month}-${day}`;
    
    return (
      <div className="date-time-display">
        <div className="date-part">{formattedDate}</div>
        <div className="time-part">{timePart}</div>
      </div>
    );
  }
  
  // Fallback to original format if parsing fails
  return dateTimeStr;
};

const columnHelper = createColumnHelper<ScheduleTableRow>();

// Define columns based on chart_two.py's table structure and desired fields
const columns = [
  // Replace op_id with a sequence number column
  {
    id: 'sequence',
    header: 'No',
    cell: ({ row }) => row.index + 1,
  },
  columnHelper.accessor('job_id', { header: 'Job ID', cell: info => info.getValue() }),
  columnHelper.accessor('scheduled_start_time_str', { 
    header: 'Start\nTime', 
    cell: info => formatDateTime(info.getValue()) 
  }),
  columnHelper.accessor('scheduled_end_time_str', { 
    header: 'End\nTime', 
    cell: info => formatDateTime(info.getValue()) 
  }),
  columnHelper.accessor('lcd_date_str', { 
    header: 'LCD Date', 
    cell: info => formatLCDDate(info.getValue()) 
  }),
  columnHelper.accessor('start_date_input_str', { 
    header: 'Req. Start', 
    cell: info => formatDateTime(info.getValue())
  }),
  columnHelper.accessor('job_dependency', { 
    header: 'Depend', 
    cell: info => {
      const value = info.getValue();
      // Convert to string for safe comparison and handle all cases
      const strValue = String(value);
      if (strValue === '1') return 'Yes';
      if (strValue === '0') return 'No';
      return value || '-';
    } 
  }),
  columnHelper.accessor('job', { header: 'Job Name', cell: info => info.getValue() || 'N/A' }),
  columnHelper.accessor('process_code', { header: 'Process Code', cell: info => info.getValue() || 'N/A' }),
  columnHelper.accessor('rsc_code', { header: 'Resource\nCode', cell: info => info.getValue() || 'N/A' }),
  columnHelper.accessor('rsc_location', { header: 'Location', cell: info => info.getValue() || 'N/A' }),
  columnHelper.accessor('number_operator', { header: 'Opr', cell: info => info.getValue() }),
  columnHelper.accessor('job_quantity', { header: 'Job Qty', cell: info => info.getValue() }),
  columnHelper.accessor('expect_output_per_hour', { header: 'Output\nPer Hr', cell: info => info.getValue() }),
  columnHelper.accessor('priority', { header: 'Priority', cell: info => info.getValue() }),
  columnHelper.accessor('hours_need', { header: 'Hours\nNeed', cell: info => info.getValue()?.toFixed(1) || '0.0' }),
  columnHelper.accessor('setting_hours', { header: 'Setting\nHr', cell: info => info.getValue()?.toFixed(1) || '0.0' }),
  columnHelper.accessor('break_hours', { header: 'Break Hr', cell: info => info.getValue()?.toFixed(1) || '0.0' }),
  columnHelper.accessor('no_prod', { header: 'No Prod Hr', cell: info => info.getValue()?.toFixed(1) || '0.0' }),
  columnHelper.accessor('accumulated_daily_output', { header: 'Accum. Output', cell: info => info.getValue() }),
  columnHelper.accessor('balance_quantity', { header: 'Bal. Qty', cell: info => info.getValue() }),
  columnHelper.accessor('bal_hr', { header: 'Bal Hr', cell: info => info.getValue()?.toFixed(1) || 'N/A' }),
  columnHelper.accessor('buffer_status', {
    header: 'Buffer\nStatus',
    cell: info => {
      const status = info.getValue();
      let statusClass = 'buffer-status buffer-status-ok';
      if (status === 'Late') statusClass = 'buffer-status buffer-status-late';
      else if (status === 'Warning') statusClass = 'buffer-status buffer-status-warning';
      else if (status === 'Caution') statusClass = 'buffer-status buffer-status-caution';
      return <span className={statusClass}>{status}</span>;
    },
  }),
];

const DetailedScheduleTable: React.FC = () => {
  const [data, setData] = useState<ScheduleTableRow[]>([]);
  const [overview, setOverview] = useState<ScheduleOverview | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([]);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [scheduleResponse, overviewResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/reports/detailed-schedule`),
          fetch(`${API_BASE_URL}/reports/schedule-overview`)
        ]);
        
        if (!scheduleResponse.ok) {
          const errorData = await scheduleResponse.json();
          throw new Error(errorData.detail || `Failed to fetch table data: ${scheduleResponse.statusText}`);
        }
        
        const fetchedData: ScheduleTableRow[] = await scheduleResponse.json();
        setData(fetchedData);
        
        if (overviewResponse.ok) {
          const overviewData: ScheduleOverview = await overviewResponse.json();
          setOverview(overviewData);
        }
      } catch (err) {
        if (err instanceof Error) {
            setError(err.message);
        } else {
            setError('An unknown error occurred while fetching table data.');
        }
        console.error("Error fetching detailed schedule data:", err);
      }
      setIsLoading(false);
    };
    fetchData();
  }, []);

  const table = useReactTable({
    data,
    columns,
    state: {
        sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (isLoading) {
    return (
      <div className="container-fluid">
        <div className="card">
          <div className="card-header">
            <h2>Detailed Production Schedule</h2>
          </div>
          <div className="card-body">
            <div className="spinner-container">
              <div className="spinner-border" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-fluid">
        <div className="card">
          <div className="card-header">
            <h2>Detailed Production Schedule</h2>
          </div>
          <div className="card-body">
            <div className="error-message">Error: {error}</div>
          </div>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="container-fluid">
        <div className="card">
          <div className="card-header">
            <h2>Detailed Production Schedule</h2>
          </div>
          <div className="card-body">
            <div className="text-center p-4">No schedule data available.</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid">
      <button 
        className="back-button" 
        onClick={() => window.history.back()}
      >
        <i className="fas fa-arrow-left"></i> Back
      </button>
      
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
                <span className="stat-value">{overview.date_range}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Total Duration:</span>
                <span className="stat-value">{overview.total_duration}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Records Displayed:</span>
                <span className="stat-value">{overview.records_displayed}</span>
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
      
      <div className="card">
        <div className="card-header">
          <h2>Detailed Production Schedule</h2>
        </div>
        <div className="card-body">
          <div className="table-responsive">
            <table className="table table-striped table-hover schedule-table">
              <thead>
                {table.getHeaderGroups().map(headerGroup => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map(header => (
                      <th
                        key={header.id}
                        onClick={header.column.getToggleSortingHandler()}
                        className={header.column.getIsSorted() ? `sort-${header.column.getIsSorted()}` : ''}
                      >
                        {formatColumnHeader(flexRender(header.column.columnDef.header, header.getContext()))}
                        {{
                          asc: ' ↑',
                          desc: ' ↓',
                        }[header.column.getIsSorted() as string] ?? null}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map(row => (
                  <tr key={row.id}>
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DetailedScheduleTable; 