# Security foundation

Current services expose only a public informational page and process health/API documentation. Development binds to loopback. No accounts, secrets, provider calls, or database exist.

- Keep local `.env` files out of Git; `.env.example` contains safe examples only. Use deployment secret storage later.
- Never log connection strings, tokens, passwords, or authorization headers. Browser `VITE_*` values are public.
- Review dependency updates and lockfile diffs; run lint, build, and tests before merging.
- Validate symbols, ranges, limits, and payload sizes when real endpoints are added. Return stable errors without exposing raw provider/database exceptions.
- Choose password/session handling, CSRF protections, rate limits, and ownership checks before account implementation. Do not invent custom cryptography.
- No CORS middleware is needed while the landing page makes no API calls. Configure explicit allowed origins when integration begins.
- Use HTTPS in deployment. Keep training artifacts trusted and versioned; never deserialize untrusted pickle/joblib files.
- If a secret is exposed, revoke/rotate it and notify the team; deleting the file alone is insufficient.

Educational use does not remove the need to protect user data. Do not claim predictions are investment advice or guaranteed outcomes.
