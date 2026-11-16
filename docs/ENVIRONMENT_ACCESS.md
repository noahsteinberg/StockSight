# Diagnose agent execution access

## Current findings (November 16, 2026)

The ordinary sandboxed agent command process reports Windows Low Mandatory Level. Its Docker
named-pipe connection is permission-denied and localhost TCP requests fail with
an explicit socket-access prohibition. The account already belongs to docker-users.
Docker context desktop-linux selects the expected Docker Desktop Linux-engine pipe.

In the continuation session, the supported command approval mechanism allowed
the same virtual-environment diagnostic outside the sandbox. That process
reported Medium Mandatory Level, accessible Docker and accessible PostgreSQL
on port 5433. Ports 8000 and 5173 were unavailable (not denied). Run Docker and
live database/HTTP verification through that approved execution path; ordinary
sandbox commands still cannot establish service reachability. No configuration
or system-protection change was needed. Screen capture remained off.

The readable user config selects windows.sandbox = elevated. This is a sandbox
implementation choice, not proof that agent commands have administrator access
or permission to contact Docker. Active session/managed policy can impose further
restrictions; changing a user default cannot guarantee it overrides that policy.

The November 15 database evidence records successful PostgreSQL/browser runs.
That establishes prior recorded success, not the exact old token/policy or proof
of which application update or setting caused the difference. No current process
can be assumed to have the permissions of a prior session.

The GitHub connector's separate 403 Resource not accessible by integration is a
service-side write-access problem. Fixing local socket access will not itself
grant that connector repository write permissions.

## Repeatable comparison

From backend, in the agent runner and then in your normal PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe -m app.environment_check --require-docker
```

The command is read-only. It reports Docker access, process integrity level and
localhost TCP connectivity for database 5433, API 8000 and frontend 5173. It never
prints passwords, connection URLs, raw group membership or email identifiers.
Not listening means no service answered; permission denied means this process
was forbidden to make the connection. A low token alone is not a complete
diagnosis; compare it with the actual access results.

If the normal terminal succeeds while the agent is denied, resolve the agent's
execution policy rather than changing database credentials or application logic.
If both fail, inspect Docker's engine state and host access independently.

## What can be fixed in the repository

- Backend completion now checks Docker access before installing dependencies or
  validating millions of rows. A denied environment fails immediately.
- AGENTS.md tells future sessions to run this check before live integration work.
- Use a unique directory under backend/.pytest_cache for pytest --basetemp;
  the redirected sandbox TEMP previously prevented ordinary temporary-file setup.
- The existing one-command backend setup can perform migration/import/verification
  from a permitted execution environment.

These changes improve detection and automation; they do not grant OS permissions.

## Remaining environment configuration

The next local coding session needs project writes, local-service networking and
a supported approval path for Docker commands that exceed its sandbox. Use the
narrowest supported permissions. A permission policy that automatically rejects
those requests cannot be overcome by retrying a command or editing project code.

OpenAI documents sandbox access separately from approval policy, and documents
that the Windows elevated implementation still executes commands without
administrator privileges. Network-proxy profiles block local/private addresses
unless explicitly allowed; a localhost allow rule alone does not establish
Windows named-pipe access. Do not use the documented Unix docker.sock example as
though it configured the Windows npipe endpoint.

The active managed session cannot be reconfigured from inside this repository.
Use its supported command approval mechanism when available, as verified above.
If that mechanism is unavailable or rejects access, any further permitted access
change must be applied through app/device configuration outside the session and
verified with the same diagnostic.
Do not disable system protections or expose an unauthenticated Docker TCP API.

Official references:

- https://learn.chatgpt.com/docs/windows/windows-sandbox
- https://learn.chatgpt.com/docs/permissions
- https://learn.chatgpt.com/docs/agent-approvals-security
