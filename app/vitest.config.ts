import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  test: {
    passWithNoTests: true,
    globals: true,
    environment: 'node',
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
    exclude: ['**/node_modules/**', '**/dist/**', '**/.databricks/**'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './client/src'),
    },
  },
});
