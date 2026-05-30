import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// A SPA é servida pelo FastAPI sob /app, portanto o base path precisa casar.
// O build gera os estáticos diretamente em src/api/static/spa (artefato único).
// Em dev, o proxy encaminha /api e /consultar-projetos-lei etc. ao backend :8000.
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  build: {
    outDir: '../src/api/static/spa',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true, ws: true },
      '/consultar-projetos-lei': { target: 'http://localhost:8000', changeOrigin: true },
      '/analise-legislativa': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
