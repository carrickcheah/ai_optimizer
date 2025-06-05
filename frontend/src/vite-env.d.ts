/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  // Add other custom VITE_ environment variables here if you have them
  // Vite's built-in variables like MODE, DEV, PROD, BASE_URL will be available automatically
  // thanks to the /// <reference types="vite/client" />
}

// By removing the explicit "interface ImportMeta" declaration,
// TypeScript will correctly merge your custom "ImportMetaEnv" variables
// with Vite's default environment variables. 