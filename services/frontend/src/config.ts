/**
 * Application configuration
 */

// API base URL - hardcoded temporarily for debugging
export const API_BASE_URL = "http://localhost:8000/api";

// Comment out the environment variable version for now
// const envApiBaseUrl = import.meta.env.VITE_API_BASE_URL;
// if (!envApiBaseUrl) {
//   console.warn("VITE_API_BASE_URL is not set. Falling back to default or erroring. Ensure it's defined in your .env file for local development or in your CI/CD environment for deployments.");
// }