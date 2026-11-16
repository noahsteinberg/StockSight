import { defineConfig } from '@playwright/test';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('..', import.meta.url));
const apiApp = process.env.STOCKSIGHT_E2E_DATABASE_URL ? 'app.main:app' : 'app.demo:create_demo_app --factory';
const python = process.env.STOCKSIGHT_PYTHON || path.join(root, 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
export default defineConfig({
  testDir: './e2e',
  testIgnore: 'accounts.spec.js',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5174', browserName: 'chromium', headless: true, trace: 'retain-on-failure' },
  webServer: [
    { command: `"${python}" -m uvicorn ${apiApp} --host 127.0.0.1 --port 8101`, cwd: path.join(root, 'backend'), url: 'http://127.0.0.1:8101/api/health', env: { STOCKSIGHT_DATABASE_URL: process.env.STOCKSIGHT_E2E_DATABASE_URL || '' }, reuseExistingServer: false },
    { command: 'npm run dev -- --port 5174', url: 'http://127.0.0.1:5174', env: { STOCKSIGHT_API_TARGET: 'http://127.0.0.1:8101' }, reuseExistingServer: false },
  ],
});
