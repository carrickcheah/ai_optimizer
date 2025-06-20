import React, { useState, useEffect, useMemo } from 'react';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { useDataCache } from '../contexts/DataCacheContext';
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
  MachineName_v?: string;  // Machine name field
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
    cell: ({ row }: { row: any }) => row.index + 1,
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
  columnHelper.accessor('job', { header: 'Job Name', cell: info => info.getValue() || 'N/A' }),
  columnHelper.accessor('process_code', { header: 'Process Code', cell: info => info.getValue() || 'N/A' }),
  columnHelper.accessor('MachineName_v', { header: 'Machine Name', cell: info => info.getValue() || 'N/A' }),
  // Removed Location column as requested
  columnHelper.accessor('number_operator', { header: 'Opr', cell: info => info.getValue() }),
  columnHelper.accessor('job_quantity', { header: 'Job Qty', cell: info => info.getValue() }),
  columnHelper.accessor('expect_output_per_hour', { header: 'Output\nPer Hr', cell: info => info.getValue() }),
  columnHelper.accessor('priority', { header: 'Priority', cell: info => info.getValue() }),
  columnHelper.accessor('hours_need', { header: 'Hours\nNeed', cell: info => info.getValue()?.toFixed(1) || '0.0' }),
  columnHelper.accessor('setting_hours', { header: 'Setting\nHr', cell: info => info.getValue()?.toFixed(1) || '0.0' }),
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
  const { data: cacheData } = useDataCache();
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
    itemsPerPage: 500, // Default to 500 to show all jobs
  });

  // Use cached data instead of local state
  const allData = cacheData.detailedSchedule;
  const isLoading = cacheData.isLoading;
  const error = cacheData.error;
  const lastRefresh = cacheData.lastRefresh;

  // Apply client-side pagination to cached data (memoized to prevent re-renders)
  const data = useMemo(() => {
    const startIndex = (pagination.currentPage - 1) * pagination.itemsPerPage;
    const endIndex = startIndex + pagination.itemsPerPage;
    return allData.slice(startIndex, endIndex);
  }, [allData, pagination.currentPage, pagination.itemsPerPage]);

  const rowOptions = [50, 100, 250, 500]; // Options for rows per page

  // Data loading strategy parameters (for display only - actual config from backend .env)
  const DATA_LOADING_CONFIG = {
    planningHorizonDays: 180,  // Backend: 180-day planning horizon from .env
    maxJobsLimit: 1000,        // Backend: MAX_JOBS_LIMIT from .env  
    refreshType: 'manual'      // Manual refresh via "Refreshing All Data" button
  };

  // No automatic data loading - user must click refresh button

  // Update pagination when cached data changes
  useEffect(() => {
    if (allData.length > 0) {
      // Update pagination state for client-side pagination
      setPagination(prev => ({
        ...prev,
        totalPages: Math.ceil(allData.length / prev.itemsPerPage),
        totalItems: allData.length
      }));
    }
  }, [allData, isLoading]);


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
            <div className="text-center p-4">
              No schedule data available.
              <br />
              <small>Debug: allData={allData.length}, data={data.length}, loading={isLoading.toString()}</small>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <button 
          className="back-button" 
          onClick={() => window.history.back()}
        >
          <i className="fas fa-arrow-left"></i> Back
        </button>
      </div>
      
      {/* Schedule Overview Section */}
      {allData.length > 0 && (
        <div className="overview-section">
          <div className="overview-left">
            <h3>Schedule Overview</h3>
            <div className="overview-stats">
              <div className="stat-item">
                <span className="stat-label">Total Jobs:</span>
                <span className="stat-value">{allData.length}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Date Range:</span>
                <span className="stat-value">{
                  (() => {
                    if (allData.length === 0) return 'N/A';
                    const dates = allData.map(job => [job.scheduled_start_time_str, job.scheduled_end_time_str]).flat().filter(d => d);
                    if (dates.length === 0) return 'N/A';
                    
                    // Extract dates from datetime strings
                    const extractedDates = dates.map(dateStr => {
                      if (dateStr && dateStr.includes(' ')) {
                        return dateStr.split(' ')[0]; // Get just the date part
                      }
                      return dateStr;
                    }).filter(d => d);
                    
                    if (extractedDates.length === 0) return 'N/A';
                    
                    const sortedDates = extractedDates.sort();
                    const earliest = sortedDates[0];
                    const latest = sortedDates[sortedDates.length - 1];
                    return earliest === latest ? earliest : `${earliest} to ${latest}`;
                  })()
                }</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Work Duration:</span>
                <span className="stat-value">{
                  (() => {
                    if (allData.length === 0) return '0 hours';
                    const totalHours = allData.reduce((total, job) => total + (job.hours_need || 0), 0);
                    return `${Math.round(totalHours).toLocaleString()} hours`;
                  })()
                }</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Records Displayed:</span>
                <span className="stat-value">{data.length}</span>
              </div>
            </div>
          </div>
          
          <div className="overview-right">
            <h3>Buffer Status</h3>
            <div className="buffer-overview">
              <div className="buffer-rows">
                {(() => {
                  // Memoized buffer status calculation to prevent infinite loops
                  const bufferCounts = useMemo(() => {
                    const counts = {
                      Late: allData.filter(job => job.buffer_status === 'Late').length,
                      Warning: allData.filter(job => job.buffer_status === 'Warning').length,
                      Caution: allData.filter(job => job.buffer_status === 'Caution').length,
                      OK: allData.filter(job => job.buffer_status === 'OK').length,
                      'Unscheduled': allData.filter(job => 
                        job.buffer_status !== 'Late' && 
                        job.buffer_status !== 'Warning' && 
                        job.buffer_status !== 'Caution' && 
                        job.buffer_status !== 'OK'
                      ).length
                    };
                    
                    return counts;
                  }, [allData]);
                  const totalJobs = allData.length || 1; // Avoid division by zero
                  
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
                      
                      <div className="buffer-row">
                        <div className="buffer-label buffer-label-unscheduled">Unscheduled</div>
                        <div className="buffer-bar-container">
                          <div 
                            className="buffer-bar-fill buffer-unscheduled" 
                            style={{ width: `${(bufferCounts['Unscheduled'] / totalJobs) * 100}%` }}
                          >
                            <span className="buffer-count">{bufferCounts['Unscheduled']} jobs</span>
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

      {/* Priority Legend */}
      {allData.length > 0 && (
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
          <div className="priority-item">
            <span className="priority-color" style={{ backgroundColor: '#cccccc' }}></span>
            <span className="priority-label">Unscheduled jobs</span>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h2>Detailed Production Schedule</h2>
          <div className="header-info">
            <small className="text-light">
              Planning horizon: {DATA_LOADING_CONFIG.planningHorizonDays} days | 
              Max jobs: {DATA_LOADING_CONFIG.maxJobsLimit} | 
              Refresh: Manual via dashboard button | 
              Last refresh: {lastRefresh.toLocaleTimeString()}
            </small>
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