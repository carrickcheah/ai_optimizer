const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') }); // Adjusted path to point to root .env

const environment = {
  NODE_ENV: process.env.NODE_ENV || 'development',
  PORT: process.env.PORT || 3000,
  SESSION_SECRET: process.env.SESSION_SECRET || 'nexerp-secret-key',
  SUPABASE_URL: process.env.SUPABASE_URL,
  SUPABASE_KEY: process.env.SUPABASE_KEY,
  DB_HOST: process.env.DB_HOST || process.env.MARIADB_HOST,
  DB_USER: process.env.DB_USER || process.env.MARIADB_USERNAME,
  DB_NAME: process.env.DB_NAME || process.env.MARIADB_DATABASE,
  DB_PASSWORD: process.env.DB_PASSWORD || process.env.MARIADB_PASSWORD,
};

// Optional: Log loaded environment variables for debugging (only in development)
if (environment.NODE_ENV === 'development') {
  console.log('Loaded Environment Variables:');
  console.log('PORT:', environment.PORT);
  console.log('DB_HOST:', environment.DB_HOST);
  console.log('DB_USER:', environment.DB_USER);
  console.log('DB_NAME:', environment.DB_NAME);
  console.log('DB_PASSWORD:', environment.DB_PASSWORD ? '********' : undefined);
  console.log('SUPABASE_URL:', environment.SUPABASE_URL ? 'Loaded' : 'Missing');
  console.log('SUPABASE_KEY:', environment.SUPABASE_KEY ? 'Loaded' : 'Missing');
  console.log('NODE_ENV:', environment.NODE_ENV);

  if (!environment.SUPABASE_URL || !environment.SUPABASE_KEY) {
    console.error('Supabase URL or Key is missing. Check .env file.');
  }
}

module.exports = environment;
