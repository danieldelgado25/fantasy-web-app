import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Standard Vite + React setup. Dev server runs on :5173 by default; the
// Flask API runs on :5000 (see backend/run.py) — that's why app.py enables
// CORS for /api/*, rather than trying to proxy requests through Vite.
export default defineConfig({
  plugins: [react()],
});
