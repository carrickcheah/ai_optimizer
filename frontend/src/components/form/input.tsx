import React, { useState, useEffect } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import './input.css';
import '../header.css';
import { useParams, useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../../config';

// Form data interface
interface FormData {
  op_id?: number; // Added for edit mode
  lcd_date: Date | null;
  job: string;
  process_code: string;
  rsc_location: string;
  rsc_code: string;
  number_operator: number;
  job_quantity: string;
  expect_output_per_hour: string;
  hours_need: string;
  setting_hours: number;
  break_hours: number;
  no_prod: number;
  priority: number;
  job_dependency: boolean;
  material_arrival: Date | null;
  start_date: Date | null;
  reduce_operation_hours: number;
}

// Added interface for machine data
interface Machine {
  MachineName_v: string;
}

// Labels for form fields
const formLabels = {
  title: 'Jobs Form',
  lcd_date: 'LCD Date & Time',
  job: 'Job',
  process_code: 'Process Code',
  rsc_location: 'Resource Location',
  rsc_code: 'Resource Code',
  number_operator: 'Number of Operators',
  job_quantity: 'Job Quantity',
  expect_output_per_hour: 'Expected Output Per Hour',
  hours_need: 'Hours Needed',
  setting_hours: 'Setting Hours',
  break_hours: 'Break Hours',
  no_prod: 'No Production Hours',
  priority: 'Priority',
  job_dependency: 'Job Dependency',
  material_arrival: 'Material Arrival Time',
  start_date: 'Start Date & Time',
  reduce_operation_hours: 'Reduce Non-Productive Times',
  submit: 'Submit',
  reset: 'Reset',
};

const InputForm: React.FC = () => {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const [isEditMode, setIsEditMode] = useState<boolean>(!!id);
  const [isLoading, setIsLoading] = useState<boolean>(!!id);
  const [error, setError] = useState<string | null>(null);
  
  // New state for machine names
  const [machines, setMachines] = useState<Machine[]>([]);
  const [loadingMachines, setLoadingMachines] = useState<boolean>(true);
  
  const [formData, setFormData] = useState<FormData>({
    lcd_date: null,
    job: '',
    process_code: '',
    rsc_location: '',
    rsc_code: '',
    number_operator: 1,
    job_quantity: '',
    expect_output_per_hour: '',
    hours_need: '0.00',
    setting_hours: 1,
    break_hours: 1,
    no_prod: 8,
    priority: 3,
    job_dependency: true,
    material_arrival: null,
    start_date: null,
    reduce_operation_hours: 0,
  });

  // useEffect for auto-calculating hours_need
  useEffect(() => {
    const jobQtyNum = parseFloat(formData.job_quantity);
    const outputPerHourNum = parseFloat(formData.expect_output_per_hour);

    if (!isNaN(jobQtyNum) && !isNaN(outputPerHourNum) && outputPerHourNum > 0) {
      const calculatedHours = jobQtyNum / outputPerHourNum;
      setFormData(prevFormData => ({
        ...prevFormData,
        hours_need: calculatedHours.toFixed(2)
      }));
    } else {
      setFormData(prevFormData => ({
        ...prevFormData,
        hours_need: '0.00' 
      }));
    }
  }, [formData.job_quantity, formData.expect_output_per_hour]);

  // Track raw input values for number fields to make typing easier
  const [numberInputs, setNumberInputs] = useState({
    setting_hours: '1',
    break_hours: '1',
    no_prod: '8',
    priority: '3',
    number_operator: '1'
  });

  // Helper function to validate numeric input
  const validateNumericInput = (value: string, allowDecimals = false): string => {
    // Empty values become empty string
    if (value === '') return '';
    
    if (allowDecimals) {
      // Allow one decimal point and digits
      // Replace multiple decimals with single decimal
      let sanitized = value.replace(/\.+/g, '.');
      // Remove non-digit and non-decimal characters
      sanitized = sanitized.replace(/[^\d.]/g, '');
      // Ensure only one decimal point exists
      const parts = sanitized.split('.');
      if (parts.length > 2) {
        sanitized = parts[0] + '.' + parts.slice(1).join('');
      }
      return sanitized;
    } else {
      // Only allow digits
      return value.replace(/\D/g, '');
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type } = e.target;
    
    // Special case for text-based fields that should be integers or floats
    if (name === 'job_quantity' || name === 'expect_output_per_hour') {
      const sanitizedValue = validateNumericInput(value, false); // Integers only for these two
      setFormData({
        ...formData,
        [name]: sanitizedValue
      });
    }
    else if (type === 'number') {
      // Update the raw input value for typing experience
      setNumberInputs({
        ...numberInputs,
        [name]: value
      });
      
      // Also update the numeric value in formData if it's a valid number
      if (value === '' || value === '-' || value === '.') {
        // Keep formData as 0 for these intermediate values
        setFormData({
          ...formData,
          [name]: 0
        });
      } else {
        const numValue = parseFloat(value);
        if (!isNaN(numValue)) {
          setFormData({
            ...formData,
            [name]: numValue
          });
        }
      }
    } else {
      // For text inputs, just update formData directly
      setFormData({
        ...formData,
        [name]: value
      });
    }
  };

  const handleDateChange = (date: Date | null, fieldName: string) => {
    setFormData({
      ...formData,
      [fieldName]: date
    });
  };

  const formatDateForSubmission = (date: Date | null): string | null => {
    if (!date) return null;
    try {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0'); // Month is 0-indexed
      const day = String(date.getDate()).padStart(2, '0');
      
      // Safety check for year
      if (year < 1000 || year > 9999) {
        console.warn(`Year ${year} is out of expected range.`);
        return '';
      }
      
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`; // Changed to YYYY-MM-DD HH:MM:SS
    } catch (error) {
      console.error("Error formatting date:", error);
      return '';
    }
  };

  // Parse date string from API to Date object
  const parseDateFromAPI = (dateString: string | null): Date | null => {
    if (!dateString) return null;
    try {
      return new Date(dateString);
    } catch (err) {
      console.error("Error parsing date:", err);
      return null;
    }
  };

  // Fetch job data if in edit mode
  useEffect(() => {
    if (isEditMode && id) {
      setIsLoading(true);
      setError(null);
      
      fetch(`${API_BASE_URL}/production-jobs/${id}`)
        .then(response => {
          if (!response.ok) {
            return response.text().then(text => { 
              throw new Error(`Server responded with ${response.status}: ${text}`);
            });
          }
          return response.json();
        })
        .then(data => {
          console.log('Fetched job data:', data);
          
          // Update form data with the fetched values
          setFormData({
            op_id: data.op_id,
            lcd_date: parseDateFromAPI(data.lcd_date),
            job: data.job,
            process_code: data.process_code,
            rsc_location: data.rsc_location,
            rsc_code: data.rsc_code,
            number_operator: data.number_operator,
            job_quantity: data.job_quantity.toString(),
            expect_output_per_hour: data.expect_output_per_hour.toString(),
            hours_need: data.hours_need.toString(),
            setting_hours: data.setting_hours,
            break_hours: data.break_hours,
            no_prod: data.no_prod,
            priority: data.priority,
            job_dependency: data.job_dependency,
            material_arrival: parseDateFromAPI(data.material_arrival),
            start_date: parseDateFromAPI(data.start_date),
            reduce_operation_hours: data.reduce_operation_hours,
          });
          
          // Also update numberInputs for proper display
          setNumberInputs({
            setting_hours: data.setting_hours.toString(),
            break_hours: data.break_hours.toString(),
            no_prod: data.no_prod.toString(),
            priority: data.priority.toString(),
            number_operator: data.number_operator.toString()
          });
        })
        .catch(error => {
          console.error('Error fetching job data:', error);
          setError(`Failed to load job: ${error.message}`);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [id, isEditMode]);

  // Fetch machine names from the database
  useEffect(() => {
    setLoadingMachines(true);
    
    console.log('Fetching machines from:', `${API_BASE_URL}/machines`);
    
    fetch(`${API_BASE_URL}/machines`)
      .then(response => {
        console.log('Machines API response status:', response.status);
        if (!response.ok) {
          return response.text().then(text => { 
            console.error('Machines API error response:', text);
            throw new Error(`Server responded with ${response.status}: ${text}`);
          });
        }
        return response.json();
      })
      .then(data => {
        console.log('Fetched machine data:', data);
        console.log('Number of machines:', data.length);
        setMachines(data);
      })
      .catch(error => {
        console.error('Error fetching machine data:', error);
        setError(`Failed to load machines: ${error.message}`);
        // Set fallback machines for development
        setMachines([
          { MachineName_v: "Machine1" },
          { MachineName_v: "Machine2" },
          { MachineName_v: "Machine3" }
        ]);
      })
      .finally(() => {
        setLoadingMachines(false);
      });
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const submittedData = {
      ...formData,
      lcd_date: formatDateForSubmission(formData.lcd_date),
      material_arrival: formatDateForSubmission(formData.material_arrival),
      start_date: formatDateForSubmission(formData.start_date),
    };

    console.log(`Form data being sent to backend for ${isEditMode ? 'update' : 'creation'}:`, submittedData);

    // Determine URL and HTTP method based on whether we're editing or creating
    const url = isEditMode 
      ? `${API_BASE_URL}/production-jobs/${id}` 
      : `${API_BASE_URL}/production-jobs`;
    
    const method = isEditMode ? 'PUT' : 'POST';

    fetch(url, {
      method: method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(submittedData),
    })
      .then(response => {
        if (!response.ok) {
          return response.text().then(text => { 
            throw new Error(`Server responded with ${response.status}: ${text}`);
          });
        }
        return response.json();
      })
      .then(data => {
        console.log('Success response from backend:', data);
        alert(`Job ${isEditMode ? 'updated' : 'submitted'} successfully!`);
        
        if (isEditMode) {
          // Navigate back to the view page
          navigate(`/job/view/${id}`);
        } else {
          // Reset form for new submission
          handleReset();
        }
      })
      .catch(error => {
        console.error(`Error ${isEditMode ? 'updating' : 'submitting'} form:`, error);
        alert(`Error ${isEditMode ? 'updating' : 'submitting'} job: ${error.message}`);
      });
  };

  const handleReset = () => {
    setFormData({
      lcd_date: null,
      job: '',
      process_code: '',
      rsc_location: '',
      rsc_code: '',
      number_operator: 1,
      job_quantity: '',
      expect_output_per_hour: '',
      hours_need: '0.00',
      setting_hours: 1,
      break_hours: 1,
      no_prod: 8,
      priority: 3,
      job_dependency: true,
      material_arrival: null,
      start_date: null,
      reduce_operation_hours: 0,
    });
    
    // Reset the string values for number inputs
    setNumberInputs({
      setting_hours: '1',
      break_hours: '1',
      no_prod: '8',
      priority: '3',
      number_operator: '1'
    });
  };

  // Add handler for select changes (for dropdown fields like job_dependency and rsc_code)
  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    if (name === 'job_dependency') {
      setFormData({
        ...formData,
        [name]: value === 'true' // Convert string 'true'/'false' to actual boolean
      });
    } else if (name === 'reduce_operation_hours') {
      setFormData({
        ...formData,
        [name]: parseInt(value, 10) // Convert string to number
      });
    } else {
      // For other select elements like rsc_code
      setFormData({
        ...formData,
        [name]: value
      });
    }
  };

  return (
    <div className="input-form-container">
      {isLoading ? (
        <div className="loading-container">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          <p>Loading job data...</p>
        </div>
      ) : error ? (
        <div className="error-container">
          <div className="alert alert-danger">
            <i className="fas fa-exclamation-circle me-2"></i>{error}
          </div>
          <button className="btn btn-primary" onClick={() => navigate(-1)}>Go Back</button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="production-form">
          <h2>{isEditMode ? 'Edit Job' : formLabels.title}</h2>
          
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="lcd_date">{formLabels.lcd_date}</label>
              <DatePicker
                id="lcd_date"
                selected={formData.lcd_date}
                onChange={(date: Date | null) => handleDateChange(date, 'lcd_date')}
                showTimeSelect
                timeFormat="HH:mm"
                timeIntervals={15}
                dateFormat="dd/MM/yyyy HH:mm:ss"
                className="date-picker-input"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="job">{formLabels.job}</label>
              <input
                type="text"
                id="job"
                name="job"
                value={formData.job}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="process_code">{formLabels.process_code}</label>
              <input
                type="text"
                id="process_code"
                name="process_code"
                value={formData.process_code}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="rsc_location">{formLabels.rsc_location}</label>
              <input
                type="text"
                id="rsc_location"
                name="rsc_location"
                value={formData.rsc_location}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="rsc_code">{formLabels.rsc_code}</label>
              {loadingMachines ? (
                <div className="d-flex align-items-center">
                  <div className="spinner-border spinner-border-sm text-primary me-2" role="status">
                    <span className="visually-hidden">Loading machines...</span>
                  </div>
                  <span>Loading machines...</span>
                </div>
              ) : machines.length === 0 ? (
                <div className="text-warning">
                  <i className="fas fa-exclamation-triangle me-1"></i>
                  No machines available. Check API connection.
                </div>
              ) : (
                <select
                  id="rsc_code"
                  name="rsc_code"
                  value={formData.rsc_code}
                  onChange={handleSelectChange}
                  className="form-select"
                  required
                >
                  <option value="">Select a machine</option>
                  {machines.map((machine, index) => (
                    <option key={`${machine.MachineName_v}-${index}`} value={machine.MachineName_v}>
                      {machine.MachineName_v}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="job_dependency">{formLabels.job_dependency}</label>
              <select
                id="job_dependency"
                name="job_dependency"
                value={formData.job_dependency.toString()}
                onChange={handleSelectChange}
                className="form-select"
                required
              >
                <option value="false">No</option>
                <option value="true">Yes</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="job_quantity">{formLabels.job_quantity}</label>
              <input
                type="text"
                id="job_quantity"
                name="job_quantity"
                value={formData.job_quantity}
                onChange={handleInputChange}
                pattern="[0-9]*"
                inputMode="numeric"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="expect_output_per_hour">{formLabels.expect_output_per_hour}</label>
              <input
                type="text"
                id="expect_output_per_hour"
                name="expect_output_per_hour"
                value={formData.expect_output_per_hour}
                onChange={handleInputChange}
                pattern="[0-9]*"
                inputMode="numeric"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="hours_need">{formLabels.hours_need}</label>
              <input
                type="text"
                id="hours_need"
                name="hours_need"
                value={formData.hours_need}
                readOnly
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="setting_hours">{formLabels.setting_hours}</label>
              <input
                type="number"
                id="setting_hours"
                name="setting_hours"
                value={numberInputs.setting_hours}
                onChange={handleInputChange}
                min="0"
                step="any"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="break_hours">{formLabels.break_hours}</label>
              <input
                type="number"
                id="break_hours"
                name="break_hours"
                value={numberInputs.break_hours}
                onChange={handleInputChange}
                min="0"
                step="any"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="no_prod">{formLabels.no_prod}</label>
              <input
                type="number"
                id="no_prod"
                name="no_prod"
                value={numberInputs.no_prod}
                onChange={handleInputChange}
                min="0"
                step="any"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="priority">{formLabels.priority}</label>
              <input
                type="number"
                id="priority"
                name="priority"
                value={numberInputs.priority}
                onChange={handleInputChange}
                min="1"
                max="5"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="number_operator">{formLabels.number_operator}</label>
              <input
                type="number"
                id="number_operator"
                name="number_operator"
                value={numberInputs.number_operator}
                onChange={handleInputChange}
                min="0"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="material_arrival">{formLabels.material_arrival}</label>
              <DatePicker
                id="material_arrival"
                selected={formData.material_arrival}
                onChange={(date: Date | null) => handleDateChange(date, 'material_arrival')}
                showTimeSelect
                timeFormat="HH:mm"
                timeIntervals={15}
                dateFormat="dd/MM/yyyy HH:mm:ss"
                className="date-picker-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="start_date">{formLabels.start_date}</label>
              <DatePicker
                id="start_date"
                selected={formData.start_date}
                onChange={(date: Date | null) => handleDateChange(date, 'start_date')}
                showTimeSelect
                timeFormat="HH:mm"
                timeIntervals={15}
                dateFormat="dd/MM/yyyy HH:mm:ss"
                className="date-picker-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="reduce_operation_hours">{formLabels.reduce_operation_hours}</label>
              <select
                id="reduce_operation_hours"
                name="reduce_operation_hours"
                value={formData.reduce_operation_hours.toString()}
                onChange={handleSelectChange}
                className="form-select"
                required
              >
                <option value="0">Normal</option>
                <option value="1">-50%</option>
                <option value="2">-100%</option>
              </select>
            </div>
          </div>

          <div className="form-buttons">
            <button type="submit" className="submit-btn">
              {isEditMode ? 'Update Job' : formLabels.submit}
            </button>
            {isEditMode ? (
              <button type="button" className="cancel-btn" onClick={() => navigate(`/job/view/${id}`)}>
                Cancel
              </button>
            ) : (
              <button type="button" className="reset-btn" onClick={handleReset}>
                {formLabels.reset}
              </button>
            )}
          </div>
        </form>
      )}
    </div>
  );
};

export default InputForm;
