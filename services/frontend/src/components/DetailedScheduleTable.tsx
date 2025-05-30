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
  plan_date?: string;  // New field for plan date
  lcd_date_str?: string;
  LCD_DATE?: string;
  lcd_date?: string;
  due_date?: string;
  target_date?: string;
  job?: string;
  process_code?: string;
  job_dependency?: string;
  rsc_location?: string;  // Will not be displayed but keep in interface
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
  if (!dateTimeStr || dateTimeStr === 'N/A') return 'N/A';

  // The backend returns LCD date in format: "dd/mm/yy HH:MM"
  // This should be displayed as-is or can be reformatted if needed
  
  try {
    // If it's already in the expected format (dd/mm/yy HH:MM), return as-is
    if (/^\d{2}\/\d{2}\/\d{2} \d{2}:\d{2}$/.test(dateTimeStr)) {
      return dateTimeStr;
    }
    
    // Try to parse other possible formats and convert to dd/mm/yy HH:MM
    let date: Date | null = null;
    
    // Try parsing as ISO date string
    if (dateTimeStr.includes('-') && (dateTimeStr.includes('T') || dateTimeStr.includes(' '))) {
      date = new Date(dateTimeStr);
    }
    
    if (date && !isNaN(date.getTime())) {
      // Format as dd/mm/yy HH:MM
      const day = date.getDate().toString().padStart(2, '0');
      const month = (date.getMonth() + 1).toString().padStart(2, '0');
      const year = date.getFullYear().toString().slice(-2);
      const hours = date.getHours().toString().padStart(2, '0');
      const minutes = date.getMinutes().toString().padStart(2, '0');
      
      return `${day}/${month}/${year} ${hours}:${minutes}`;
    }
    
    // If all parsing fails, return the original value
    return dateTimeStr;
    
  } catch (error) {
    console.warn('Error formatting LCD date:', dateTimeStr, error);
    return dateTimeStr;
  }
};

// Helper function specifically for LCD Date and Req Start format (YYYY-MM-DD \n HH:MM)
const formatDateTimeSpecial = (dateTimeStr: string | undefined): React.ReactNode => {
  if (!dateTimeStr || dateTimeStr === 'N/A') return 'N/A';
  
  try {
    let date: Date | null = null;
    
    // Try parsing different possible formats
    if (dateTimeStr.includes('/')) {
      // Handle dd/mm/yy HH:MM format
      const match = dateTimeStr.match(/^(\d{2})\/(\d{2})\/(\d{2}) (\d{2}):(\d{2})$/);
      if (match) {
        const [, day, month, year, hours, minutes] = match;
        const fullYear = 2000 + parseInt(year); // Convert yy to yyyy
        date = new Date(fullYear, parseInt(month) - 1, parseInt(day), parseInt(hours), parseInt(minutes));
      }
    } else if (dateTimeStr.includes('-')) {
      // Handle YYYY-MM-DD HH:MM:SS or YYYY-MM-DD HH:MM format
      date = new Date(dateTimeStr);
    }
    
    if (date && !isNaN(date.getTime())) {
      // Format as YYYY-MM-DD on top line, HH:MM on bottom line
      const dateStr = date.getFullYear() + '-' + 
                     (date.getMonth() + 1).toString().padStart(2, '0') + '-' + 
                     date.getDate().toString().padStart(2, '0');
      const timeStr = date.getHours().toString().padStart(2, '0') + ':' + 
                     date.getMinutes().toString().padStart(2, '0');
      
      return (
        <div className="date-time-display">
          <div className="date-part">{dateStr}</div>
          <div className="time-part">  {timeStr}</div>
        </div>
      );
    }
    
    // If parsing fails, return the original value
    return dateTimeStr;
    
  } catch (error) {
    console.warn('Error formatting date:', dateTimeStr, error);
    return dateTimeStr;
  }
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
  // Add Plan Date column
  columnHelper.accessor('plan_date', { 
    header: 'Plan Date', 
    cell: info => formatDateTime(info.getValue()) 
  }),
  // Removed Job ID column as requested
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
    cell: info => {
      const row = info.row.original;
      // Try different field names that might contain LCD date
      const lcdValue = row.lcd_date_str || row.LCD_DATE || row.lcd_date || row.due_date || row.target_date;
      return formatDateTimeSpecial(lcdValue);
    }
  }),
  columnHelper.accessor('start_date_input_str', { 
    header: 'Req. Start', 
    cell: info => formatDateTimeSpecial(info.getValue())
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
  // Removed Location column as requested
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
  const [pagination, setPagination] = useState<{
    currentPage: number;
    totalPages: number;
    totalItems: number;
    itemsPerPage: number;
  }>({
    currentPage: 1,
    totalPages: 1,
    totalItems: 0,
    itemsPerPage: 50, // Default to 50
  });

  const rowOptions = [50, 100, 250, 500]; // Options for rows per page

  useEffect(() => {
    const fetchData = async (currentPage = pagination.currentPage, itemsPerPage = pagination.itemsPerPage) => {
      setIsLoading(true);
      setError(null);
      try {
        // Construct query parameters for pagination
        const scheduleParams = new URLSearchParams({
          page: currentPage.toString(),
          page_size: itemsPerPage.toString(),
          // Add other existing params like sort_field, sort_order if needed by this endpoint
        });

        // Assuming detailed-schedule endpoint supports pagination
        const scheduleUrl = `${API_BASE_URL}/reports/detailed-schedule?${scheduleParams.toString()}`;
        const overviewUrl = `${API_BASE_URL}/reports/schedule-overview`; // Assuming overview doesn't need pagination

        const [scheduleResponse, overviewResponse] = await Promise.all([
          fetch(scheduleUrl),
          fetch(overviewUrl)
        ]);
        
        if (!scheduleResponse.ok) {
          const errorData = await scheduleResponse.json();
          throw new Error(errorData.detail || `Failed to fetch table data: ${scheduleResponse.statusText}`);
        }
        
        // Assuming API returns pagination info along with items
        const scheduleResult = await scheduleResponse.json(); 
        const resultData = scheduleResult.items || scheduleResult;
        
        setData(resultData); // Handle if API returns array directly or object with items
        
        // Update pagination state from API response if available
        // This part needs to be adapted based on the actual API response structure for this endpoint
        setPagination(prev => ({
          ...prev,
          currentPage: scheduleResult.page || currentPage,
          totalPages: scheduleResult.total_pages || Math.ceil((scheduleResult.total_items || (scheduleResult.items || scheduleResult).length) / itemsPerPage),
          totalItems: scheduleResult.total_items || (scheduleResult.items || scheduleResult).length,
          itemsPerPage: scheduleResult.page_size || itemsPerPage,
        }));
        
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
  }, [pagination.currentPage, pagination.itemsPerPage]); // Re-fetch when page or itemsPerPage changes

  const handleRowsPerPageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newItemsPerPage = parseInt(e.target.value);
    // Call fetchData directly or update state to trigger useEffect
    setPagination(prev => ({ ...prev, itemsPerPage: newItemsPerPage, currentPage: 1 })); 
  };

  const handlePageChange = (pageNumber: number) => {
    if (pageNumber < 1 || pageNumber > pagination.totalPages) return;
    setPagination(prev => ({ ...prev, currentPage: pageNumber }));
  };

  const renderTableInfo = () => {
    const { currentPage, itemsPerPage, totalItems } = pagination;
    const start = totalItems === 0 ? 0 : (currentPage - 1) * itemsPerPage + 1;
    const end = Math.min(start + itemsPerPage - 1, totalItems);
    return `Showing ${start} to ${end} of ${totalItems} entries`;
  };

  const renderPaginationControls = () => {
    const { currentPage, totalPages } = pagination;
    const maxPagesToShow = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);
    startPage = Math.max(1, endPage - maxPagesToShow + 1);

    const pages: React.ReactElement[] = [];
    pages.push(
      <li key="prev" className={`page-item ${currentPage === 1 ? 'disabled' : ''}`}>
        <button className="page-link" onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1}>&laquo;</button>
      </li>
    );
    if (startPage > 1) {
      pages.push(<li key="1" className="page-item"><button className="page-link" onClick={() => handlePageChange(1)}>1</button></li>);
      if (startPage > 2) pages.push(<li key="ellipsis1" className="page-item disabled"><span className="page-link">...</span></li>);
    }
    for (let i = startPage; i <= endPage; i++) {
      pages.push(
        <li key={i} className={`page-item ${i === currentPage ? 'active' : ''}`}>
          <button className="page-link" onClick={() => handlePageChange(i)}>{i}</button>
        </li>
      );
    }
    if (endPage < totalPages) {
      if (endPage < totalPages - 1) pages.push(<li key="ellipsis2" className="page-item disabled"><span className="page-link">...</span></li>);
      pages.push(<li key={totalPages} className="page-item"><button className="page-link" onClick={() => handlePageChange(totalPages)}>{totalPages}</button></li>);
    }
    pages.push(
      <li key="next" className={`page-item ${currentPage === totalPages ? 'disabled' : ''}`}>
        <button className="page-link" onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages}>&raquo;</button>
      </li>
    );
    return <ul className="pagination">{pages}</ul>;
  };

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
          <div className="schedule-subtitle">
            Showing 50 jobs with optimized rolling window (7-day buffer, 30-day horizon)
          </div>
        </div>
        <div className="card-body">
          <div className="row mb-3">
            <div className="col-md-6">
              {/* Placeholder for any future search/filter controls */}
            </div>
            <div className="col-md-6 text-end">
              <div className="d-flex justify-content-end align-items-center">
                <label htmlFor="rowsPerPageDetailed" className="me-2 text-nowrap">Show</label>
                <select 
                  id="rowsPerPageDetailed" 
                  className="form-select me-2" 
                  style={{ width: 'auto' }}
                  value={pagination.itemsPerPage}
                  onChange={handleRowsPerPageChange}
                >
                  {rowOptions.map(option => (
                    <option key={option} value={option}>{option} per page</option>
                  ))}
                </select>
                <span>entries</span>
              </div>
            </div>
          </div>

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

          {/* Pagination Controls */}
          <div className="pagination-container">
            <div id="tableInfoDetailed">{renderTableInfo()}</div>
            <nav aria-label="Page navigation">
              {renderPaginationControls()}
            </nav>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DetailedScheduleTable; 