# Test Report

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start e2e -->
**Status:** failed
**Target:** sandbox
**Date:** 2026-10-16

Passed: 20 · Failed: 12 · Skipped: 0 · Flaky: 0 · Total: 32

| Spec | Status |
|---|---|
| responds 200 with an array, and each item (if any) has the documented shape | passed |
| rejects an unsupported file type with the documented accepted/rejected shape | passed |
| responds 404 for a document id that does not exist | passed |
| responds 404 for a document id that does not exist | passed |
| responds 200 with an array, most recently active first | passed |
| responds 200 with id, title and created_at, and the thread is then listed and loadable | passed |
| responds 404 for a thread id that does not exist | passed |
| renames with a 200 {id,title} shape, and rejects an empty title with 422 | passed |
| renaming an unknown thread id responds 404 | passed |
| responds 204, and the thread is unreachable and unlisted afterwards | passed |
| streams text/event-stream and ends with a persisted 'not found' reply when the shared library has no ready document | passed |
| posting to an unknown thread id responds 404 | passed |
| answer text grows progressively and citations appear on completion | passed |
| expands to show excerpt, file name and page/section, collapses unchanged, and shows deleted-source wording | failed |
| shows the did-not-complete indication and allows asking again | failed |
| a question sent from the empty composer creates a thread the backend can load independently | failed |
| the new title is readable from a fresh API call, not just from the page's own state | failed |
| the confirmation dialog warns deletion is permanent and cannot be undone | failed |
| confirming the deletion removes the row from the library and issues one DELETE | failed |
| cancelling the confirmation leaves the document present and issues no DELETE | failed |
| declares English and shows English navigation labels on every screen | passed |
| has no language switcher control anywhere in the shell | passed |
| renders on a plain light background with no unstyled or dark theme applied | passed |
| the app loads | passed |
| sidebar and chat are visible together, and switching to documents preserves the in-progress thread | passed |
| sidebar, chat and documents are each reachable via the mobile drawer with no horizontal overflow | failed |
| the drawer scrim closes the drawer without navigating away | passed |
| shows an empty-state message and a working new-conversation action | passed |
| shows its history and citations | failed |
| updates the sidebar title, and an empty rename is rejected | failed |
| with confirmation removes it from the sidebar | failed |
| returns the chat area to the empty state | failed |
<!-- sdlc:auto:end e2e -->

<!-- sdlc:auto:start unit -->
**Coverage:** backend 47.3% · frontend 84.4%

**Test cases:** 325 / 331 written

**Lines written:** 5397

**Files deferred:** 2
<!-- sdlc:auto:end unit -->

<!-- sdlc:auto:start dev-checks -->
### Sprint 6

_No test steps recorded._

### Sprint 6

| Step | Status | Ticket | Finished |
|---|---|---|---|
| run_checks | succeeded | — | 2026-10-16 |

### Sprint 5

| Step | Status | Ticket | Finished |
|---|---|---|---|
| run_checks | failed | — | 2026-10-16 |

### Sprint 4

| Step | Status | Ticket | Finished |
|---|---|---|---|
| run_checks | succeeded | — | 2026-10-16 |

### Sprint 3

| Step | Status | Ticket | Finished |
|---|---|---|---|
| run_checks | failed | — | 2026-10-16 |

### Sprint 2

| Step | Status | Ticket | Finished |
|---|---|---|---|
| run_checks | succeeded | — | 2026-10-16 |

### Sprint 1

| Step | Status | Ticket | Finished |
|---|---|---|---|
| run_checks | succeeded | — | 2026-10-16 |
<!-- sdlc:auto:end dev-checks -->
