import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const api = "http://127.0.0.1:8000";

export default defineConfig({
  base: "./", // relative asset URLs: the site works from any path, including static hosting
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/policies": api, "/estimate": api, "/samples": api, "/health": api },
  },
});
