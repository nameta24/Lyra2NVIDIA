import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  root: 'frontend',
  publicDir: path.resolve(__dirname, 'sample_scenes'),   // serves /concession_fallback.ply
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
});
