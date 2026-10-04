import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// ui_strings.json (backend) and config/referral_resources.json live outside frontend/ and are bundled at build time.
const repoRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    fs: { allow: [repoRoot] },
    proxy: { "/api": "http://localhost:8000" },
  },
  build: { outDir: "dist", target: "es2022" },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
    include: ["src/**/*.test.{ts,tsx}"],
    globals: true,
  },
});
