import React, { useState, useEffect, ReactElement, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import './table_data.css';
import { API_BASE_URL } from '../../config';

interface ProductionSchedule {
  LCD_DATE: string | null;
  JOB: string;
  PROCESS_CODE: string;
  RSC_LOCATION: string;
  RSC_CODE: string;
  MACHINE: string;
  NUMBER_OPERATOR: number;
  JOB_QUANTITY: number;
  EXPECT_OUTPUT_PER_HOUR: number | null;
  HOURS_NEED: number | null;
  DAY_NEED: number | null;
  SETTING_HOURS: number;
  BREAK_HOURS: number;
  NO_PROD: number;
  START_DATE: string;
  ACCUMULATED_DAILY_OUTPUT: number | null;
  BALANCE_QUANTITY: number;
  TxnId_i: number;
  MATERIAL_ARRIVAL: string | null;
  JOB_DEPENDENCY: boolean;
  PRIORITY: number | null;
  REDUCE_OPERATION_HOURS: number | null;
}

interface TableDataProps {
  endpoint?: string; // API endpoint URL
}

interface Pagination {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  itemsPerPage: number;
}

const TableData: React.FC<TableDataProps> = ({ endpoint = `${API_BASE_URL}/production-jobs/production-schedule` }) => {
  // Use the provided endpoint or the default one
  const apiEndpoint = endpoint;
  
  // State hooks
  const [jobs, setJobs] = useState<ProductionSchedule[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>('');
  const [sortField, setSortField] = useState<string>('LCD_DATE');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  
  // Pagination state
  const [pagination, setPagination] = useState<Pagination>({
    currentPage: 1,
    totalPages: 1,
    totalItems: 0,
    itemsPerPage: 50 // Changed from 25 to 50 to match DetailedScheduleTable style
  });
  
  // Available row options for pagination - updated to match user requirements
  const rowOptions = [50, 100, 150, 200];
  
  // Format date to display in dd/MM/yyyy format
  const formatDate = (dateString: string | null): string => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return 'N/A';
      
      const day = date.getDate().toString().padStart(2, '0');
      const month = (date.getMonth() + 1).toString().padStart(2, '0');
      const year = date.getFullYear();
      
      return `${day}/${month}/${year}`;
    } catch (err) {
      return 'N/A';
    }
  };
  
  // Format date to display in yyyy-MM-dd HH:mm:ss.SSS format
  const formatDateTimeMilliseconds = (dateString: string | null): React.ReactElement => {
    if (!dateString) return <>N/A</>; // Return JSX for N/A
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return <>N/A</>; // Return JSX for N/A

      const year = date.getFullYear();
      const month = (date.getMonth() + 1).toString().padStart(2, '0');
      const day = date.getDate().toString().padStart(2, '0');
      const hours = date.getHours().toString().padStart(2, '0');
      const minutes = date.getMinutes().toString().padStart(2, '0');
      const seconds = date.getSeconds().toString().padStart(2, '0');
      // Milliseconds are no longer needed for this display format

      const datePart = `${year}-${month}-${day}`;
      const timePart = `${hours}:${minutes}:${seconds}`;

      return (
        <>
          {datePart}
          <br />
          {timePart}
        </>
      );
    } catch (err) {
      return <>N/A</>; // Return JSX for N/A
    }
  };
  
  // Format boolean for job_dependency display
  const formatJobDependency = (value: boolean): React.ReactElement => {
    return value ? 
      <span className="badge bg-success">Yes</span> : 
      <span className="badge bg-danger">No</span>;
  };
  
  // Format reduce operation hours display
  const formatReduceHours = (value: number): string => {
    // Handle undefined, null, or non-numeric values
    if (value === undefined || value === null || isNaN(value)) {
      return 'NO';
    }
    
    // Convert to number if it's a string
    const numValue = typeof value === 'string' ? parseInt(value, 10) : Number(value);
    
    switch (numValue) {
      case 0: return 'NO';
      case 1: return '-50%';
      case 2: return '-100%';
      default: return 'NO';
    }
  };
  
  // Fetch data from API - stable reference to prevent re-renders
  const fetchData = useCallback(async (currentPage?: number, currentItemsPerPage?: number, currentSortField?: string, currentSortOrder?: 'asc' | 'desc', currentSearch?: string) => {
    // Use current state if parameters not provided
    const page = currentPage ?? pagination.currentPage;
    const pageSize = currentItemsPerPage ?? pagination.itemsPerPage;
    const field = currentSortField ?? sortField;
    const order = currentSortOrder ?? sortOrder;
    const searchTerm = currentSearch ?? search;
    
    setIsLoading(true);
    setError(null);
    
    // Construct query parameters with optimized rolling window
    const queryParams = new URLSearchParams({
      page: page.toString(),
      page_size: Math.min(pageSize, 100).toString(), // Cap at 100 for performance
      sort_field: field,
      sort_order: order,
      // Rolling window optimization - focus on time-critical jobs
      buffer_days: '10', // Changed from 30 to 1 day
      planning_horizon_days: '90', // Increased from 30 to 90 days
    });

    if (searchTerm) {
      queryParams.append('search', searchTerm);
    }

    try {
      const startTime = performance.now(); // Track loading time
      const response = await fetch(`${apiEndpoint}?${queryParams.toString()}`);
      
      if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}`);
      }
      
      const data = await response.json(); // Expecting { items: [], total_items: 0, ... }
      const endTime = performance.now();
      
      console.log(`API call took ${(endTime - startTime).toFixed(2)}ms - Total items: ${data.total_items}, Config:`, data.data_loading_config);
      
      setJobs(data.items || []); // Update jobs with data.items
      
      // Update pagination info from API response
      setPagination({
        currentPage: data.page || 1,
        totalPages: data.total_pages || 1,
        totalItems: data.total_items || 0,
        itemsPerPage: data.page_size || 50
      });
      
    } catch (err) {
      setError(`Failed to fetch data: ${err instanceof Error ? err.message : 'Unknown error'}`);
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [endpoint]); // Only depend on endpoint
  
  // Handle sorting
  const handleSort = (field: string) => {
    const newOrder = field === sortField && sortOrder === 'asc' ? 'desc' : 'asc';
    setSortField(field);
    setSortOrder(newOrder);
    fetchData(1, pagination.itemsPerPage, field, newOrder); // Fetch data from backend
  };
  
  // Handle search with debouncing to prevent excessive API calls
  const [searchTerm, setSearchTerm] = useState<string>('');
  
  // Debounced search effect
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchTerm !== search) { // Only update if search actually changed
      setSearch(searchTerm);
        fetchData(1, pagination.itemsPerPage, sortField, sortOrder, searchTerm);
      }
    }, 500); // 500ms debounce
    
    return () => clearTimeout(timeoutId);
  }, [searchTerm]); // Only depend on searchTerm
  
  // Handle search input change - now updates searchTerm instead of search directly
  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value);
  };
  
  // Handle apply filters button - now redundant with debouncing but kept for manual trigger
  const applyFilters = () => {
    setSearch(searchTerm); // Force immediate search
  };
  
  // Handle rows per page change
  const handleRowsPerPageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newItemsPerPage = parseInt(e.target.value);
    fetchData(1, newItemsPerPage, sortField, sortOrder); // Fetch data from backend
  };
  
  // Handle page change
  const handlePageChange = (pageNumber: number) => {
    if (pageNumber < 1 || pageNumber > pagination.totalPages) return;
    fetchData(pageNumber, pagination.itemsPerPage, sortField, sortOrder); // Fetch data from backend
  };
  
  // Handle delete button click
  const handleDelete = (id: number) => {
    if (window.confirm('Are you sure you want to delete this job? This action cannot be undone.')) {
      // In a real app, this would make a DELETE request to the API
      console.log(`Delete job with ID: ${id}`);
      // Then refetch data
      // fetchData();
    }
  };
  
  // Generate pagination controls
  const renderPagination = () => {
    const { currentPage, totalPages } = pagination;
    const maxPagesToShow = 5;
    
    let startPage = Math.max(1, currentPage - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);
    
    // Adjust start page if end page is maxed out
    startPage = Math.max(1, endPage - maxPagesToShow + 1);
    
    const pages: React.ReactElement[] = [];
    
    // Previous button
    pages.push(
      <li key="prev" className={`page-item ${currentPage === 1 ? 'disabled' : ''}`}>
        <button className="page-link" onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1}>
          &laquo;
        </button>
      </li>
    );
    
    // First page and ellipsis if needed
    if (startPage > 1) {
      pages.push(
        <li key="1" className="page-item">
          <button className="page-link" onClick={() => handlePageChange(1)}>1</button>
        </li>
      );
      if (startPage > 2) {
        pages.push(<li key="ellipsis1" className="page-item disabled"><span className="page-link">...</span></li>);
      }
    }
    
    // Page numbers
    for (let i = startPage; i <= endPage; i++) {
      pages.push(
        <li key={i} className={`page-item ${i === currentPage ? 'active' : ''}`}>
          <button className="page-link" onClick={() => handlePageChange(i)}>{i}</button>
        </li>
      );
    }
    
    // Last page and ellipsis if needed
    if (endPage < totalPages) {
      if (endPage < totalPages - 1) {
        pages.push(<li key="ellipsis2" className="page-item disabled"><span className="page-link">...</span></li>);
      }
      pages.push(
        <li key={totalPages} className="page-item">
          <button className="page-link" onClick={() => handlePageChange(totalPages)}>{totalPages}</button>
        </li>
      );
    }
    
    // Next button
    pages.push(
      <li key="next" className={`page-item ${currentPage === totalPages ? 'disabled' : ''}`}>
        <button className="page-link" onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages}>
          &raquo;
        </button>
      </li>
    );
    
    return (
      <ul className="pagination">
        {pages}
      </ul>
    );
  };
  
  // Table info text (e.g. "Showing 1 to 50 of 200 entries")
  const renderTableInfo = () => {
    const { currentPage, itemsPerPage, totalItems } = pagination;
    const start = totalItems === 0 ? 0 : (currentPage - 1) * itemsPerPage + 1;
    const end = Math.min(start + itemsPerPage - 1, totalItems);
    
    return `Showing ${start} to ${end} of ${totalItems} entries`;
  };
  
  // Effect hook to fetch data when component mounts - only run once
  useEffect(() => {
    fetchData();
  }, [fetchData]); // Depend on fetchData which is now stable
  
  // Filter and sort jobs - Now handled by backend, just return jobs - memoized for performance
  const displayedJobs = useMemo(() => {
    return jobs; // Data is already sorted and paginated by backend
  }, [jobs]);
  
  return (
    <div className="container-fluid mt-4">
      {/* Error message display */}
      {error && (
        <div className="alert alert-danger alert-dismissible fade show" role="alert">
          <i className="fas fa-exclamation-circle me-2"></i>{error}
          <button type="button" className="btn-close" onClick={() => setError(null)}></button>
        </div>
      )}
      
      <div className="row">
        <div className="col-12">
          <button 
            className="back-button" 
            onClick={() => window.history.back()}
          >
            <i className="fas fa-arrow-left"></i> Back
          </button>
          <div className="card">
            <div className="card-header">
              <span className="fs-5">Production Jobs</span>
            </div>
            
            <div className="card-body">
              {/* Search and filter controls */}
              <div className="row mb-3">
                <div className="col-md-6">
                  <div className="input-group">
                    <span className="input-group-text">
                      <i className="fas fa-search"></i>
                    </span>
                    <input 
                      type="text" 
                      id="searchInput" 
                      className="form-control" 
                      placeholder="Search job, process code..." 
                      value={searchTerm}
                      onChange={handleSearch}
                      onKeyDown={(e) => e.key === 'Enter' && applyFilters()}
                    />
                    <button 
                      id="applyFilters" 
                      className="btn btn-primary ms-2"
                      onClick={applyFilters}
                    >
                      <i className="fas fa-filter me-1"></i>Apply Filters
                    </button>
                  </div>
                </div>
                <div className="col-md-6 text-end">
                  <div className="d-flex justify-content-end align-items-center">
                    <label className="me-2 text-nowrap">Show</label>
                    <select 
                      id="rowsPerPage" 
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
              
              {/* Jobs Table */}
              <div className="table-responsive">
                <table id="jobsTable" className="table table-hover">
                  <thead>
                    <tr>
                      <th className={`text-center sortable ${sortField === 'LCD_DATE' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('LCD_DATE')}>
                        LCD<br/>DATE
                      </th>
                      <th className={`text-center sortable ${sortField === 'TxnId_i' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('TxnId_i')}>
                        TXN<br/>ID
                      </th>
                      <th className={`text-center sortable ${sortField === 'START_DATE' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('START_DATE')}>
                        START<br/>DATE
                      </th>
                      <th className={`text-center sortable ${sortField === 'MATERIAL_ARRIVAL' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('MATERIAL_ARRIVAL')}>
                        MATERIAL<br/>ARRIVAL
                      </th>
                      <th className={`text-center sortable ${sortField === 'JOB' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('JOB')}>
                        JOB
                      </th>
                      <th className={`text-center sortable ${sortField === 'PROCESS_CODE' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('PROCESS_CODE')}>
                        PROCESS<br/>CODE
                      </th>
                      <th className={`text-center sortable ${sortField === 'MACHINE' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('MACHINE')}>
                        MACHINE<br/>NAME
                      </th>
                      <th className={`text-center sortable ${sortField === 'JOB_DEPENDENCY' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('JOB_DEPENDENCY')}>
                        JOB<br/>DEPEND
                      </th>
                      <th className={`text-center sortable ${sortField === 'NUMBER_OPERATOR' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('NUMBER_OPERATOR')}>
                        NO<br/>OPR
                      </th>
                      <th className={`text-center sortable ${sortField === 'JOB_QUANTITY' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('JOB_QUANTITY')}>
                        JOB<br/>QUANTITY
                      </th>
                      <th className={`text-center sortable ${sortField === 'ACCUMULATED_DAILY_OUTPUT' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('ACCUMULATED_DAILY_OUTPUT')}>
                        DAILY<br/>OUTPUT
                      </th>
                      <th className={`text-center sortable ${sortField === 'BALANCE_QUANTITY' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('BALANCE_QUANTITY')}>
                        BALANCE<br/>QUANTITY
                      </th>
                      <th className={`text-center sortable ${sortField === 'REDUCE_OPERATION_HOURS' ? `sort-${sortOrder}` : ''}`}
                          onClick={() => handleSort('REDUCE_OPERATION_HOURS')}>
                        REDUCE<br/>HRS
                      </th>
                      <th className="text-center">ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody id="jobsTableBody">
                    {isLoading ? (
                      <tr>
                        <td colSpan={14} className="text-center py-4">
                          <div className="spinner-border text-primary" role="status">
                            <span className="visually-hidden">Loading...</span>
                          </div>
                          <p className="mt-2">Loading production schedule...</p>
                        </td>
                      </tr>
                    ) : displayedJobs.length === 0 ? (
                      <tr>
                                                  <td colSpan={14} className="text-center">No production schedule found</td>
                      </tr>
                    ) : (
                      displayedJobs.map((job, index) => (
                        <tr key={`${job.TxnId_i}-${index}`}>
                          <td className="text-center">{formatDate(job.LCD_DATE)}</td>
                          <td className="text-center">{job.TxnId_i}</td>
                          <td className="text-center">{formatDateTimeMilliseconds(job.START_DATE)}</td>
                          <td className="text-center">{formatDate(job.MATERIAL_ARRIVAL)}</td>
                          <td className="text-center">{job.JOB}</td>
                          <td className="text-center">{job.PROCESS_CODE}</td>
                          <td className="text-center">{job.MACHINE}</td>
                          <td className="text-center">{job.JOB_DEPENDENCY ? 'Yes' : 'No'}</td>
                          <td className="text-center">{job.NUMBER_OPERATOR}</td>
                          <td className="text-center">{job.JOB_QUANTITY}</td>
                          <td className="text-center">{job.ACCUMULATED_DAILY_OUTPUT}</td>
                          <td className="text-center">{job.BALANCE_QUANTITY}</td>
                          <td className="text-center">{job.REDUCE_OPERATION_HOURS ? formatReduceHours(job.REDUCE_OPERATION_HOURS) : 'NO'}</td>
                          <td className="text-center">
                            <Link to={`/job/view/${job.TxnId_i}`} className="action-btn action-btn-view" title="View">
                              <i className="fas fa-eye"></i>
                            </Link>
                            <Link to={`/job/edit/${job.TxnId_i}`} className="action-btn action-btn-edit" title="Edit">
                              <i className="fas fa-edit"></i>
                            </Link>
                            <button 
                              className="action-btn action-btn-delete" 
                              title="Delete"
                              onClick={() => handleDelete(job.TxnId_i)}
                            >
                              <i className="fas fa-trash"></i>
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              
              {/* Pagination */}
              <div className="pagination-container">
                <div id="tableInfo">{renderTableInfo()}</div>
                <nav aria-label="Page navigation">
                  {renderPagination()}
                </nav>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TableData;
