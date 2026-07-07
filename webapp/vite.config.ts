import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api -> the FastAPI backend so the browser makes
// same-origin requests. Override the backend URL with VITE_API_TARGET.
const target = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
