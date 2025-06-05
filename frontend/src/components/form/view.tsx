import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import './view.css';
import { API_BASE_URL } from '../../config';

interface ProductionJob {
  op_id: number;
  plan_date: string | null;
  lcd_date: string | null;
  job: string;
  process_code: string;
  rsc_location: string;
  rsc_code: string;
  job_dependency: boolean;
  number_operator: number;
  job_quantity: number;
  expect_output_per_hour: number;
  hours_need: number;
  setting_hours: number;
  break_hours: number;
  no_prod: number;
  priority: number;
  material_arrival: string | null;
  start_date: string | null;
  reduce_operation_hours: number;
}

const JobView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<ProductionJob | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Format date for display
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

  // Format datetime for display with line break
  const formatDateTime = (dateString: string | null): React.ReactElement => {
    if (!dateString) return <>N/A</>;
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return <>N/A</>;

      const year = date.getFullYear();
      const month = (date.getMonth() + 1).toString().padStart(2, '0');
      const day = date.getDate().toString().padStart(2, '0');
      const hours = date.getHours().toString().padStart(2, '0');
      const minutes = date.getMinutes().toString().padStart(2, '0');
      const seconds = date.getSeconds().toString().padStart(2, '0');

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
      return <>N/A</>;
    }
  };

  // Format reduce operation hours display
  const formatReduceOperationHours = (value: number): string => {
    switch (value) {
      case 0: return 'Normal';
      case 1: return '-50%';
      case 2: return '-100%';
      default: return 'Normal';
    }
  };

  useEffect(() => {
    const fetchJobDetails = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        // Fetch job details from API
        const response = await fetch(`${API_BASE_URL}/production-jobs/${id}`);
        
        if (!response.ok) {
          throw new Error(`Server responded with status ${response.status}`);
        }
        
        const data = await response.json();
        setJob(data);
      } catch (err) {
        setError(`Failed to fetch job details: ${err instanceof Error ? err.message : 'Unknown error'}`);
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchJobDetails();
  }, [id]);

  return (
    <div className="container mt-4">
      <div className="card">
        <div className="card-header">
          <div className="d-flex justify-content-between align-items-center">
            <h5>
              <Link to="/data" className="btn btn-primary btn-sm me-2">
                <i className="fas fa-arrow-left me-1"></i>Back to Jobs
              </Link>
              <span className="ms-2">Production Job Details</span>
            </h5>
            {job && (
              <Link to={`/job/edit/${id}`} className="btn btn-light btn-sm">
                <i className="fas fa-edit me-1"></i>Edit Job
              </Link>
            )}
          </div>
        </div>
        
        <div className="card-body">
          {isLoading ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
              <p className="mt-2">Loading job details...</p>
            </div>
          ) : error ? (
            <div className="alert alert-danger">
              <i className="fas fa-exclamation-circle me-2"></i>{error}
            </div>
          ) : job ? (
            <div className="job-details">
              <div className="row g-3">
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Job ID</label>
                    <div className="detail-value">{job.op_id}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Plan Date</label>
                    <div className="detail-value">{formatDate(job.plan_date)}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>LCD Date</label>
                    <div className="detail-value datetime-value">{formatDateTime(job.lcd_date)}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Job</label>
                    <div className="detail-value">{job.job}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Process Code</label>
                    <div className="detail-value">{job.process_code}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>RSC Location</label>
                    <div className="detail-value">{job.rsc_location}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>RSC Code</label>
                    <div className="detail-value">{job.rsc_code}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Job Dependency</label>
                    <div className="detail-value">
                      {job.job_dependency ? (
                        <span className="badge bg-success">Yes</span>
                      ) : (
                        <span className="badge bg-danger">No</span>
                      )}
                    </div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Number of Operators</label>
                    <div className="detail-value">{job.number_operator}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Job Quantity</label>
                    <div className="detail-value">{job.job_quantity}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Expected Output per Hour</label>
                    <div className="detail-value">{job.expect_output_per_hour}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Hours Needed</label>
                    <div className="detail-value">{job.hours_need}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Setting Hours</label>
                    <div className="detail-value">{job.setting_hours}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Break Hours</label>
                    <div className="detail-value">{job.break_hours}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>No Production</label>
                    <div className="detail-value">{job.no_prod}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Priority</label>
                    <div className="detail-value">{job.priority}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Material Arrival</label>
                    <div className="detail-value datetime-value">{formatDateTime(job.material_arrival)}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Start Date</label>
                    <div className="detail-value datetime-value">{formatDateTime(job.start_date)}</div>
                  </div>
                </div>
                
                <div className="col-md-6">
                  <div className="detail-group">
                    <label>Reduce Non-Productive Times</label>
                    <div className="detail-value">{formatReduceOperationHours(job.reduce_operation_hours)}</div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="alert alert-warning">
              <i className="fas fa-exclamation-triangle me-2"></i>Job not found
            </div>
          )}
        </div>
        
        <div className="card-footer text-end">
          <Link to="/data" className="btn btn-secondary me-2">
            Back to Jobs List
          </Link>
          {job && (
            <Link to={`/job/edit/${id}`} className="btn btn-primary">
              <i className="fas fa-edit me-1"></i>Edit
            </Link>
          )}
        </div>
      </div>
    </div>
  );
};

export default JobView;
