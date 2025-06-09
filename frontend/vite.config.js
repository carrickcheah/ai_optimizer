import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Listen on all interfaces for cloud deployment
    port: process.env.PORT || 3000,
    proxy: {
      // Proxy API requests to the backend
      '/api': {
        target: 'http://backend.zeabur.internal:8000', // Your FastAPI port
        changeOrigin: true,
        secure: false
      }
    }
  }
}); 