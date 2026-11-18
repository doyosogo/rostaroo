# Rostaroo project instructions

## Product and scope

Rostaroo is a workforce management application for Australian hospitality, starting with cafés, restaurants and small businesses in Adelaide. Owners and managers will organise staff and publish weekly rosters. Employees will check shifts and submit availability, leave and shift swap requests. Managers will review requests and identify overlaps and staffing conflicts.

Implement only the milestone the user has authorised. Prioritise maintainability, security, accessibility, testing and understandable architecture. Use Australian English for user-facing copy and documentation.

## Stack and engineering standards

- Use React, TypeScript, Vite, Tailwind CSS and Vitest in the frontend.
- Use Python, FastAPI, SQLAlchemy, Alembic and Pytest in the backend.
- Use PostgreSQL and Docker Compose for local database development on macOS and Apple Silicon. Use free, open-source project dependencies.
- Keep the monorepo organised around one frontend and one backend. Keep HTTP routing, settings, database code, models and business services in their own areas. Add abstractions or dependencies when they solve a current problem.
- Use semantic HTML, responsive layouts and accessible defaults. Use clear names, strict TypeScript and Python type annotations where useful.
- Keep migrations reviewable. Add schema changes through Alembic when the authorised milestone introduces data models.
- Explain important engineering choices and trade-offs so a junior developer can understand and discuss them.

## Security and privacy

- Keep credentials, tokens, private keys and local environment files out of source control, history, logs and reports. Create or check ignore rules before adding local configuration or installing dependencies.
- Read configuration from environment variables or the ignored local environment file. Keep only dummy local values in `.env.example`. Do not generate real credentials.
- Use synthetic people, accounts and organisations in development. Do not use paid APIs or external production services.
- Limit local listening addresses, exposed services and browser origins to what development requires.
- If secret exposure is suspected, stop and report it without reproducing the value.

## Working and approval workflow

- Terminal 1 is reserved for Codex. Terminal 2 is reserved for the user's Git and ordinary terminal commands. Work with project files and non-interactive terminal commands. Do not use GUI control or interactive editors.
- Never initialise a nested Git repository, commit, push, run destructive Git commands or rewrite history. Use read-only Git commands to inspect changes.
- Run relevant tests, lint, format and type checks, builds, startup checks and infrastructure validation when available. Keep the basic UI and health tests independent of PostgreSQL. Test observable behaviour and regressions.
- Report exactly what was verified and why any check could not run. Review status, diffs, ignore rules and candidate files for accidental sensitive information.
- Stop at the end of the current milestone. The user obtains ChatGPT review and approval before committing. Wait for the user to authorise the next milestone.

## Mandatory final report

Use these sections for every milestone.

1. **MILESTONE STATUS** with PASS, PARTIAL or BLOCKED.
2. **IMPLEMENTATION SUMMARY** describing what was delivered and verified.
3. **PROJECT STRUCTURE** covering important files and directories.
4. **ARCHITECTURE DECISIONS** explaining why the design was chosen.
5. **TEST RESULTS** listing validation commands and PASS, FAIL or NOT RUN.
6. **SECURITY REVIEW** covering secrets, configuration, ignore rules and repository safety.
7. **ISSUES AND LIMITATIONS** recording failures, verification gaps and manual steps.
8. **MANUAL VERIFICATION** giving exact local commands.
9. **ENGINEERING LEARNING NOTES** explaining key concepts in interview-friendly language.
10. **GIT SUMMARY** recording status, files changed and whether any commit or push occurred.
