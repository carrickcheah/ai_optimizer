const express = require('express');
const router = express.Router();
const aaController = require('../controllers/aa_controller');

// Route to get and render the production schedule EJS view
router.get('/production-schedule', aaController.renderProductionScheduleView);

// Keep this if you still want a JSON API endpoint for some reason (e.g., for other clients)
// router.get('/api/production-schedule', aaController.getProductionScheduleJson); 

module.exports = router; 