import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served from https://tejesh18.github.io/ai-hype-checker/
export default defineConfig({
  base: "/ai-hype-checker/",
  plugins: [react()],
});
