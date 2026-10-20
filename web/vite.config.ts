/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The production build is written into the Python package so that
// `pip install` / the Docker image ship the web client with the API server.
const outDir = fileURLToPath(new URL("../src/virtual_array/server/static", import.meta.url));

export default defineConfig({
  plugins: [react()],
  build: {
    outDir,
    emptyOutDir: true,
    chunkSizeWarningLimit: 4000,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "node",
  },
});
