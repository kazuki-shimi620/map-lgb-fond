import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  base: "./",
  optimizeDeps: {
    exclude: ["onnxruntime-web"]
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ["recharts"],
          leaflet: ["leaflet", "react-leaflet"],
          onnx: ["onnxruntime-web"]
        }
      }
    }
  }
});
