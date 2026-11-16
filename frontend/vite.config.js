import process from 'node:process';
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from 'node:url';

export default defineConfig(({ command, mode }) => {
  if (mode === 'e2e-accounts' && command !== 'serve') throw new Error('The account test identity fixture cannot be built for production.');
  return {
  plugins: [react()],
  resolve: { alias: mode === 'e2e-accounts' ? [{ find: /^@auth0\/auth0-react$/, replacement: fileURLToPath(new URL('./e2e/auth0-fixture.jsx', import.meta.url)) }] : [] },
  server: { host: "127.0.0.1", port: 5173, strictPort: true, proxy: { "/api": process.env.STOCKSIGHT_API_TARGET || "http://127.0.0.1:8000" } },
  };
});
