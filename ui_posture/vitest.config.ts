import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // The smoke suite drives real lazy-loaded route chunks (React.lazy) —
    // under CI/loaded dev machines a single navigation can take 4-6s, which
    // exceeds vitest's 5s per-test default and produces flaky failures.
    testTimeout: 20000,
    hookTimeout: 20000,
  },
});
