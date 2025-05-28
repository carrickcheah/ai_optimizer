const express = require('express');
const router = express.Router();
// Updated paths for supabase and environment, as authRoutes is now in config/
const supabase = require('./supabase'); 
const envConfig = require('./environment');

// Login page
router.get('/login', (req, res) => {
  if (req.session.supabase_access_token && envConfig.NODE_ENV !== 'development') {
    return res.redirect('/page/dashboard');
  }
  // Updated render path for login.ejs, now in config/
  res.render('config/login', { title: 'Login', error: req.query.error || null }); 
});

// Process login
router.post('/login', async (req, res) => {
  const { email, password } = req.body;
  if (!supabase) {
    console.error('Supabase client not initialized. Cannot process login.');
    // Updated render path for login.ejs
    return res.render('config/login', { title: 'Login', error: 'Authentication service is unavailable.' });
  }
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error) {
    console.error('Login error:', error.message);
    return res.redirect('/auth/login?error=' + encodeURIComponent(error.message)); // Redirect to /auth/login
  }

  if (data.session) {
    req.session.supabase_access_token = data.session.access_token;
    req.session.supabase_refresh_token = data.session.refresh_token;
    req.session.user = data.user; 
    res.redirect('/page/dashboard'); 
  } else {
    return res.redirect('/auth/login?error=' + encodeURIComponent('Login failed.')); // Redirect to /auth/login
  }
});

// Logout
router.get('/logout', async (req, res) => {
  if (supabase) {
    const { error } = await supabase.auth.signOut();
    if (error) {
      console.error('Logout error:', error.message);
    }
  } else {
    console.warn('Supabase client not initialized during logout.');
  }
  
  req.session.destroy(err => {
    if (err) {
      console.error('Failed to destroy session during logout:', err);
      return res.redirect('/auth/login'); // Redirect to /auth/login
    }
    res.clearCookie('connect.sid'); 
    res.redirect('/auth/login'); // Redirect to /auth/login
  });
});

module.exports = router; 