# "chat documents" web app (RAG — SDLC Documentation

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start overview -->
Build a "chat with your documents" web app (RAG chatbot) that uses Google Gemini.
There is NO sign-up, NO login and NO user accounts: anyone who opens the app uses one
shared workspace. All documents and conversations are visible to everyone using it. with history

**Documentation version:** v10
<!-- sdlc:auto:end overview -->

## Contents

<!-- sdlc:auto:start contents -->
| Document | State |
|---|---|
| [Requirements](requirements/README.md) | v3 approved |
| [Architecture](architecture/README.md) | 7 entries |
| [Development](development/README.md) | 9 entries |
| [Testing](testing/README.md) | 1 entry |
| [Deployment](deployment/README.md) | 1 entry |
| [Maintenance](maintenance/README.md) | 1 entry |
| [Data model](architecture/data-model.md) | generated |
| [API (OpenAPI)](architecture/api/openapi.yaml) | generated |
| [Decisions (ADRs)](architecture/adr/README.md) | 4 decisions |
| [Sprint plan](development/sprint-plan.md) | 6 sprints |
| [Developer guide](development/developer-guide.md) | not generated yet |
| [API reference](development/api-reference.md) | 0 routes |
| [Test report](testing/test-report.md) | failed |
| [Tests](testing/test-cases.md) | 0 tests |
| [Deployment guide](deployment/deployment-guide.md) | deployed |
| [Runbook](deployment/runbook.md) | deployed |
| [Release notes](deployment/release-notes.md) | 3 releases |
| [Traceability matrix](traceability-matrix.md) | 24 requirements |
| [Changelog](CHANGELOG.md) | 10 versions |
<!-- sdlc:auto:end contents -->

## Open gaps

<!-- sdlc:auto:start open-gaps -->
### Requirements

- No approval date or approver name is given for requirements version 3.
- Exact chunk size/overlap configuration and the number of embedding retries before marking a document 'failed' are not specified.
- Whether deletion should be restricted or made recoverable (soft-delete) was raised but not decided -- carried as an explicit open assumption (see US-005).
- Gemini error/timeout handling for chat requests does not specify retry counts or timeout thresholds (see US-007).
- No fixed delivery deadline was confirmed -- 'usable soon' is an assumption, not a committed date.
- Specific chunk size/overlap values and the number of embedding retries before failure are not specified in this input.
- AC-017 is explicitly flagged in the source as an open assumption pending a decision on restricted or recoverable (soft) deletion.
- The numeric cap value and its documented default are not specified in this input.
- Retry count and timeout threshold for Gemini chat errors are not specified.
- The exact strategy for selecting 'most recent relevant turns' when truncating long-thread context is not fully specified.
- AC-053's unrestricted, unlogged thread deletion is recorded as an open assumption of the open-access model, same as document deletion (US-005).
- AC-057's fully open access to unknown internet visitors is recorded as an accepted-risk assumption rather than a resolved security control.
- Specific rate-limit thresholds and window durations are not given, only that they must be configurable.

### Architecture

- Concurrency/capacity limits of in-process indexer at upper end of 5-25 users not quantified.
- Specific Gemini model identifiers for embeddings and generation not named in architecture input.

### Development

- No sprint dates provided.
- No per-task completion breakdown provided; only story-level delivery recorded.

### Testing

- Only one test run recorded; no per-acceptance-criteria test mapping.
- No test case names, coverage percentages, or ticket linkage provided.
- No regression, integration, or manual QA results documented.

### Deployment

- No deployment date provided.
- No deployment manifest, environment configuration, or rollback info provided.
- Backend uses raw IP with self-signed/HTTPS on port 8443—TLS certificate details not documented.

### Maintenance

- No post-deployment notes exist.
- No incident history, monitoring, or operational runbook documented.
- No backup/restore or retention policy documented despite permanent-deletion behaviour.
<!-- sdlc:auto:end open-gaps -->
