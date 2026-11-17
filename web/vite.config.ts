import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const api = "http://127.0.0.1:8000";

export default defineConfig({
  envDir: "..", // one .env at the repo root; Vite only exposes VITE_* from it
  base: "./", // relative asset URLs: the site works from any path, including static hosting
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/policies": api, "/estimate": api, "/samples": api, "/health": api, "/me": api },
  },
});
