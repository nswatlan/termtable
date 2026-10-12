import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Flask API runs on :5001 (see backend/run.py); proxying keeps the
// session cookie same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": `http://127.0.0.1:${process.env.API_PORT || 5001}`,
    },
  },
});
