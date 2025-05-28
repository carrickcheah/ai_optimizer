const mysql = require('mysql2/promise');
const path = require('path');

// Database config has its own dotenv config as a fallback,
// but the main app.js should have already loaded environment variables
try {
  require('dotenv').config({ path: path.join(__dirname, '../.env') });
} catch (err) {
  console.log('Note: No local .env file found. Using environment variables directly.');
}

// Log the available environment variables for debugging
console.log('Database config using:');
console.log('DB_HOST or MARIADB_HOST:', process.env.DB_HOST || process.env.MARIADB_HOST);
console.log('DB_USER or MARIADB_USERNAME:', process.env.DB_USER || process.env.MARIADB_USERNAME);
console.log('DB_NAME or MARIADB_DATABASE:', process.env.DB_NAME || process.env.MARIADB_DATABASE);
console.log('DB_PORT or MARIADB_PORT:', process.env.DB_PORT || process.env.MARIADB_PORT);
console.log('DB_PASSWORD/MARIADB_PASSWORD: [present]', (process.env.DB_PASSWORD || process.env.MARIADB_PASSWORD) ? true : false);

// Create a connection pool - try both sets of variable names (DB_* for local, MARIADB_* for Zeabur)
const pool = mysql.createPool({
  host: process.env.DB_HOST || process.env.MARIADB_HOST || 'localhost',
  user: process.env.DB_USER || process.env.MARIADB_USERNAME || 'myuser',
  password: process.env.DB_PASSWORD || process.env.MARIADB_PASSWORD || 'mypassword',
  database: process.env.DB_NAME || process.env.MARIADB_DATABASE || 'nex_valiant',
  port: process.env.DB_PORT || process.env.MARIADB_PORT || 3306,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});

// Test the connection
pool.getConnection()
  .then(connection => {
    console.log('Database connection established successfully');
    connection.release();
  })
  .catch(err => {
    console.error('Error connecting to database:', err);
  });

module.exports = pool; 