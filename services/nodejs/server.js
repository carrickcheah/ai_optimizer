const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const path = require('path'); // Added path module
const aaRoutes = require('./routes/aa_routes'); // aa_routes will now handle rendering tableview_gr.ejs

// Load environment variables from .env file in the current directory (services/nodejs)
dotenv.config(); 

const app = express();

// View engine setup
app.set('view engine', 'ejs');
// Assuming server.js is in services/nodejs, and .ejs files are in services/nodejs/tables
app.set('views', path.join(__dirname, 'tables')); 

// Middleware
app.use(cors()); // Enable CORS for all routes
app.use(express.json()); // Parse JSON request bodies
app.use(express.urlencoded({ extended: true })); // Parse URL-encoded request bodies

// Example for serving static assets like CSS if you create a public folder in services/nodejs
// app.use(express.static(path.join(__dirname, 'public'))); 

// Routes
// The aaRoutes will now include a route that renders the EJS template
app.use('/tables', aaRoutes); // Mount aa_routes under /tables for EJS views

// Basic error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).send('Something broke!');
});

// Start the server
const PORT = process.env.NODE_PORT || 8081;
app.listen(PORT, () => {
  console.log(`Node.js server listening on port ${PORT}`);
  console.log(`Production schedule EJS view accessible at http://localhost:${PORT}/tables/production-schedule`);
}); 