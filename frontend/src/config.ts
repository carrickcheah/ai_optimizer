/**
 * Application configuration
 */

// API base URL - use proxy in development, environment variable in production
const envApiBaseUrl = import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL = envApiBaseUrl || "/api";

// Development note: Vite proxy forwards /api requests to http://localhost:8000/api
// Production should set VITE_API_BASE_URL environment variable