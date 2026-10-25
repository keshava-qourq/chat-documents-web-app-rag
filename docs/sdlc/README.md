# "chat documents" web app (RAG — SDLC Documentation

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start overview -->
Build a "chat with your documents" web app (RAG chatbot) that uses Google Gemini.
There is NO sign-up, NO login and NO user accounts: anyone who opens the app uses one
shared workspace. All documents and conversations are visible to everyone using it. with history

**Documentation version:** v9
<!-- sdlc:auto:end overview -->

## Contents

<!-- sdlc:auto:start contents -->
| Document | State |
|---|---|
| [Requirements](requirements/README.md) | v2 approved |
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
| [Traceability matrix](traceability-matrix.md) | 22 requirements |
| [Changelog](CHANGELOG.md) | 9 versions |
<!-- sdlc:auto:end contents -->

## Open gaps

<!-- sdlc:auto:start open-gaps -->
### Requirements

- No queue/cache service exists; the mechanism by which the documents screen receives live processing-status updates (polling interval vs. push) is not specified -- relevant to US-003.
- Whether document deletion should remain fully unrestricted or move to soft-delete/restricted access is an explicitly unresolved decision (see US-005/AC-017).
- No fixed delivery deadline was provided; 'usable soon' is an assumption, not a commitment.
- The number of retries and backoff policy before a document is marked 'failed' (AC-008) is not specified.
- Mechanism for live progress updates on the documents screen (e.g. polling vs. push) is not specified, notable given no queue/cache service is in the stack.
- AC-017 explicitly records unrestricted, unrecoverable, unattributed deletion as an open assumption pending a product decision on whether to restrict or allow recovery.
- The documented default cap value (used when the operator sets none, per AC-021) is not specified in these requirements.
- The retrieval parameters that define 'most relevant chunks' (e.g. top-k, similarity threshold) are not specified in the requirements.
- The relevance threshold that decides 'sufficiently relevant' versus 'not found' (AC-026) is not quantified.
- The specific context-window/truncation policy for including 'most recent relevant turns' (AC-040) is not defined numerically.
- Which side (left/right) is designated for user vs. assistant messages is not specified.
- AC-042 records fully shared, unfiltered thread visibility (no privacy) as an open assumption rather than a finalized decision.
- The exact title-generation method and truncation length (AC-049) are not specified.
- AC-053 records unrestricted, unrecoverable, unattributed thread deletion as an open assumption pending a product decision.
- AC-057 records the full open-access risk (any finder of the URL has full read/write/delete access) as an accepted but still-open assumption.
- Concrete rate-limit values (requests per window, window length) are not specified, only that they are configurable (AC-064).

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
