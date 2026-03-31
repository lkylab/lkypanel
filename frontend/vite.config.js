import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';

export default defineConfig({
  plugins: [vue()],
  root: resolve(__dirname, 'src'),
  base: '/static/dist/',
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: resolve(__dirname, '../lkypanel/static/dist'),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'src/main.js'),
        dashboard: resolve(__dirname, 'src/js/dashboard.js'),
        notifications: resolve(__dirname, 'src/js/notifications.js'),
      }
    },
  },
});
