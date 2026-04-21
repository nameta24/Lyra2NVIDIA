import { defineConfig } from 'vite';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: 'frontend',
  publicDir: path.resolve(__dirname, 'sample_scenes'),
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
    outDir: '../dist',
    emptyOutDir: true,
    rollupOptions: {
      // three is loaded via CDN importmap at runtime — don't bundle it
      external: ['three', /^three\/.*/],
    },
  },
});