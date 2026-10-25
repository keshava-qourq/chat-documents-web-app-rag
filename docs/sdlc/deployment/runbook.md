# Runbook

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start health -->
- Backend: `https://34.204.217.28:8443/apps/080e9ceea596/health`
- Frontend: https://p080e9ceea596.dwzhwrawu50o7.amplifyapp.com
<!-- sdlc:auto:end health -->

<!-- sdlc:auto:start deploy -->
Push to `main` to run `.github/workflows/deploy.yml`, or start a deployment from the platform's Deployment tab.
<!-- sdlc:auto:end deploy -->

<!-- sdlc:auto:start rollback -->
Redeploy the last good version from the platform's Deployment tab, or revert the offending commit on `main` — the workflow redeploys.

**Last live version:** a5588d689738 (`a5588d6`)
<!-- sdlc:auto:end rollback -->

<!-- sdlc:auto:start recent-failures -->
| Date | Version | Summary |
|---|---|---|
| 2026-10-19 | 0b8fa3d818ee | Could not enable the required extensions on aisdlc_080e9ceea5964933: extension "vector" is not available DETAIL:  Could not open extension control file "/usr/local/share/postgresql/extension/vector.control": No such file or directory. HINT:  The extension must first be installed on the system where PostgreSQL is running. |
| 2026-10-19 | b121a640d719 | The container could not be started: The container started but never answered its own /health after 10 attempts. |
| 2026-10-19 | 58edfcdde4cb | The container could not be started: The container started but never answered its own /health after 10 attempts. |
| 2026-10-19 | 0b8fa3d818ee | Nothing was deployed: The deployment configuration was incomplete when the workflow was published. |
<!-- sdlc:auto:end recent-failures -->

## Contacts and escalation

_Add on-call contacts here — this section is never overwritten._
