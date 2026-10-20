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
    // jsdom gives component tests a DOM; pure-logic tests run fine under it too.
    environment: "jsdom",
    // Browser smoke tests in e2e/ run under Playwright, not Vitest.
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/__tests__/setup.ts"],
    coverage: {
      provider: "v8",
      // Report every source file, not only those a unit test happens to import.
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/__tests__/**"],
      reporter: ["text-summary", "html"],
    },
  },
});
