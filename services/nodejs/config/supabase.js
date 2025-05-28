const { createClient } = require('@supabase/supabase-js');
const { SUPABASE_URL, SUPABASE_KEY, NODE_ENV } = require('./environment');

let supabase;

if (SUPABASE_URL && SUPABASE_KEY) {
  supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
} else {
  if (NODE_ENV === 'development') {
    // In development, we might allow the app to run without Supabase for certain features,
    // or use a mock. For now, just log an error and supabase will be undefined.
    console.error('Supabase client could not be initialized due to missing URL or Key. This might be okay in development if Supabase is not strictly needed for all features.');
  }
  // In production, you might want to throw an error to prevent the app from starting:
  // else if (NODE_ENV === 'production') {
  //   throw new Error('SupABASE_URL and SUPABASE_KEY must be defined in production');
  // }
}

module.exports = supabase;
