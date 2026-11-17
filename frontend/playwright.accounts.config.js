import { defineConfig } from '@playwright/test';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('..', import.meta.url));
const python = process.env.STOCKSIGHT_PYTHON || path.join(root, 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
export default defineConfig({
  testDir: './e2e', testMatch: ['accounts.spec.js', 'embedded.spec.js'], workers: 1, retries: 0, reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5175', browserName: 'chromium', headless: true, trace: 'off', video: 'off', screenshot: 'off' },
  webServer: [
    { command: `"${python}" -m uvicorn e2e_accounts_app:create_e2e_app --factory --app-dir tests --host 127.0.0.1 --port 8102`, cwd: path.join(root, 'backend'), url: 'http://127.0.0.1:8102/api/ready', reuseExistingServer: false },
    { command: 'npm run dev -- --mode e2e-accounts --port 5175', url: 'http://127.0.0.1:5175', reuseExistingServer: false,
      env: { STOCKSIGHT_API_TARGET: 'http://127.0.0.1:8102', VITE_AUTH0_DOMAIN: 'e2e.auth0.test', VITE_AUTH0_CLIENT_ID: 'test-only-client', VITE_AUTH0_AUDIENCE: 'https://stocksight-test-api' } },
    { command: 'npm run dev -- --port 5176', url: 'http://127.0.0.1:5176', reuseExistingServer: false,
      env: { STOCKSIGHT_API_TARGET: 'http://127.0.0.1:8102', VITE_AUTH0_DOMAIN: 'e2e.auth0.test', VITE_AUTH0_CLIENT_ID: 'test-only-client', VITE_AUTH0_AUDIENCE: 'https://stocksight-test-api' } },
  ],
});
