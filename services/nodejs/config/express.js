const session = require('express-session');
const { SESSION_SECRET, NODE_ENV } = require('./environment');

const sessionConfig = session({
  secret: SESSION_SECRET,
  resave: false,
  saveUninitialized: true,
  cookie: {
    secure: NODE_ENV === 'production', // Set to true in production with HTTPS
    httpOnly: true, // Helps prevent XSS attacks
    // sameSite: 'lax' // Helps prevent CSRF attacks, consider 'strict' if appropriate
  }
});

module.exports = {
  sessionConfig
};
