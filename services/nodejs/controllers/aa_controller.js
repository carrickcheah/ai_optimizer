const ProductionSchedule = require('../models/aa_model');
const { validationResult, query } = require('express-validator');

exports.getProductionSchedule = async (req, res) => {
  // Validation rules for query parameters
  const validations = [
    query('page').optional().isInt({ min: 1 }).toInt().withMessage('Page must be a positive integer'),
    query('pageSize').optional().isInt({ min: 1, max: 500 }).toInt().withMessage('Page size must be between 1 and 500'),
    query('sortField').optional().isString().trim().escape().withMessage('Sort field must be a string'),
    query('sortOrder').optional().isIn(['ASC', 'DESC', 'asc', 'desc']).toUpperCase().withMessage('Sort order must be ASC or DESC'),
    query('search').optional().isString().trim().escape().withMessage('Search term must be a string')
  ];

  // Run validations
  await Promise.all(validations.map(validation => validation.run(req)));
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }

  try {
    const { page, pageSize, sortField, sortOrder, search } = req.query;
    const scheduleData = await ProductionSchedule.findAll({
      page: page,
      pageSize: pageSize,
      sortField: sortField,
      sortOrder: sortOrder,
      search: search
    });

    const totalPages = Math.ceil(scheduleData.totalItems / scheduleData.pageSize);

    res.json({
      items: scheduleData.items,
      totalItems: scheduleData.totalItems,
      page: scheduleData.page,
      pageSize: scheduleData.pageSize,
      totalPages: totalPages
    });
  } catch (error) {
    console.error('Error fetching production schedule:', error);
    res.status(500).json({ message: 'Failed to fetch production schedule', error: error.message });
  }
};

// New method to render the EJS view
exports.renderProductionScheduleView = async (req, res) => {
  // Validation rules for query parameters (similar to before)
  const validations = [
    query('page').optional().isInt({ min: 1 }).toInt().withMessage('Page must be a positive integer'),
    query('pageSize').optional().isInt({ min: 1, max: 500 }).toInt().withMessage('Page size must be between 1 and 500'),
    query('sortField').optional().isString().trim().escape().withMessage('Sort field must be a string'),
    query('sortOrder').optional().isIn(['ASC', 'DESC', 'asc', 'desc']).toUpperCase().withMessage('Sort order must be ASC or DESC'),
    query('search').optional().isString().trim().escape().withMessage('Search term must be a string')
  ];

  await Promise.all(validations.map(validation => validation.run(req)));
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    // Handle validation errors, perhaps by rendering an error page or redirecting with a message
    // For simplicity, sending a 400 error for now
    return res.status(400).send('Validation Error: ' + JSON.stringify(errors.array()));
  }

  try {
    const page = parseInt(req.query.page) || 1;
    const pageSize = parseInt(req.query.pageSize) || 50;
    const sortField = req.query.sortField || 'LCD_DATE';
    const sortOrder = (req.query.sortOrder || 'ASC').toUpperCase();
    const search = req.query.search || '';

    const scheduleData = await ProductionSchedule.findAll({
      page: page,
      pageSize: pageSize,
      sortField: sortField,
      sortOrder: sortOrder,
      search: search
    });

    const totalPages = Math.ceil(scheduleData.totalItems / pageSize);
    const currentQuery = req.query; // Pass current query params for pagination/sorting links

    res.render('tableview_gr', { // Renders tableview_gr.ejs
      jobs: scheduleData.items,
      totalItems: scheduleData.totalItems,
      currentPage: page,
      pageSize: pageSize,
      totalPages: totalPages,
      sortField: sortField,
      sortOrder: sortOrder,
      search: search,
      currentQuery: currentQuery, // For building links
      // Helper function for EJS to build query strings
      buildQueryString: (params) => {
        return Object.entries(params)
          .filter(([key, value]) => value !== undefined && value !== '')
          .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
          .join('&');
      }
    });
  } catch (error) {
    console.error('Error rendering production schedule view:', error);
    res.status(500).send('Failed to load production schedule. ' + error.message);
  }
};

// This method can be kept if you still need a JSON API for other purposes
// exports.getProductionScheduleJson = async (req, res) => { ... previous JSON logic ... }; 