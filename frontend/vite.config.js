import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  publicDir: '../sample_scenes',
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'https://lyra2nvidia-production.up.railway.app',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});