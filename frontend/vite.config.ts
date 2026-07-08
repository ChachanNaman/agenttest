import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND_URL = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": BACKEND_URL,
      "/ws": {
        target: BACKEND_URL.replace("http", "ws"),
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
