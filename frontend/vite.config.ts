import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/static/frontend/dist/",
  plugins: [react()],
  build: {
    outDir: "static/frontend/dist",
    emptyOutDir: true,
    sourcemap: true,
    rollupOptions: {
      input: "src/main.tsx",
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (assetInfo) => assetInfo.names?.some((name) => name.endsWith(".css")) ? "app.css" : "assets/[name]-[hash][extname]"
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8003",
      "/media": "http://127.0.0.1:8003",
      "/admin": "http://127.0.0.1:8003"
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"]
  }
});
