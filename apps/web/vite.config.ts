/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const proofCore = fileURLToPath(new URL("../../packages/proof-core/ts/src/index.ts", import.meta.url));
const api = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@ledgeit/proof-core": proofCore },
    dedupe: ["@noble/hashes", "@noble/ed25519"],
  },
  build: {
    rollupOptions: {
      output: { manualChunks: { react: ["react", "react-dom", "react-router-dom", "@tanstack/react-query"], charts: ["recharts"] } },
    },
  },
  server: {
    port: 5173,
    proxy: { "/api": { target: api, changeOrigin: true, ws: true } },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
