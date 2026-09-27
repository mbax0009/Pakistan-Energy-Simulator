import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  build: {
    outDir: "dist/client",
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("/node_modules/zrender/")) return "zrender";
          if (id.includes("/node_modules/echarts/")) return "echarts";
          if (
            id.includes("/node_modules/echarts-for-react/")
            || id.includes("/node_modules/size-sensor/")
          ) return "echarts-react";
          return undefined;
        },
      },
    },
  },
  optimizeDeps: {
    include: ["react", "react-dom/client"],
  },
  server: {
    host: "0.0.0.0",
    allowedHosts: ["terminal.local"],
    warmup: {
      clientFiles: ["./src/main.jsx"],
    },
    proxy: {
      "/api": "http://127.0.0.1:8765",
    },
  },
  plugins: [react()],
});
