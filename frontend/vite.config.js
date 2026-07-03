import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В dev (npm run dev) относительные запросы к API проксируем на локальный бэкенд,
// чтобы фронт работал так же, как за nginx в контейнере (тот же origin, base="").
const apiProxy = { target: "http://localhost:8000", changeOrigin: true };

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": apiProxy,
      "/admin": apiProxy,
      "/health": apiProxy,
    },
  },
});
