# Tests

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start summary -->
202 tests · Passed 158 · Failed 0 · Skipped 0 · Not run 44

Acceptance criteria covered: 10/83 · passing: 10/83
<!-- sdlc:auto:end summary -->

<!-- sdlc:auto:start tests -->
## Sprint 1: Sprint 1 - Foundation & Upload

### US-001: Upload documents from the browser

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| — | test_delete_removes_document_from_the_shared_list_for_all_clients | Unit | Passed | `backend/tests/test_documents.py` |
| — | test_every_documents_route_succeeds_with_no_authentication | Unit | Passed | `backend/tests/test_documents.py` |
| — | test_list_documents_exposes_required_fields_and_is_identical_for_every_client | Unit | Passed | `backend/tests/test_documents.py` |
| — | test_mixed_batch_attributes_failure_to_its_own_file_and_keeps_valid_ones | Unit | Passed | `backend/tests/test_documents.py` |
| — | test_oversized_file_rejected_while_valid_file_in_same_request_is_stored | Unit | Passed | `backend/tests/test_documents.py` |
| — | test_status_endpoint_returns_404_for_an_unknown_document | Unit | Passed | `backend/tests/test_documents.py` |
| — | test_status_endpoint_returns_failure_reason_for_a_failed_document | Unit | Passed | `backend/tests/test_documents.py` |
| — | test_upload_accepts_all_four_supported_formats_and_they_appear_in_list | Unit | Passed | `backend/tests/test_documents.py` |
| — | test_upload_rejects_unsupported_formats_and_creates_no_document_row | Unit | Passed | `backend/tests/test_documents.py` |

### US-018: Navigate a responsive two-area layout

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| — | App shell > keeps the chat panel mounted (not torn down) after a round trip to Documents | Unit | Passed | `frontend/src/App.shell.test.tsx` |
| — | App shell > makes chat, documents and setup reachable from the nav | Unit | Passed | `frontend/src/App.shell.test.tsx` |
| — | App shell > offers a mobile menu toggle that opens and closes a nav drawer | Unit | Passed | `frontend/src/App.shell.test.tsx` |
| — | App shell > redirects an unknown route to chat without any login gate | Unit | Passed | `frontend/src/App.shell.test.tsx` |
| — | declares English and shows English navigation labels on every screen | E2E | Not run yet | `frontend/e2e/english-only-neutral-style.spec.ts` |
| — | has no language switcher control anywhere in the shell | E2E | Not run yet | `frontend/e2e/english-only-neutral-style.spec.ts` |
| — | renders on a plain light background with no unstyled or dark theme applied | E2E | Not run yet | `frontend/e2e/english-only-neutral-style.spec.ts` |
| — | sidebar and chat are visible together, and switching to documents preserves the in-progress thread | E2E | Not run yet | `frontend/e2e/responsive-layout.spec.ts` |
| — | sidebar, chat and documents are each reachable via the mobile drawer with no horizontal overflow | E2E | Not run yet | `frontend/e2e/responsive-layout.spec.ts` |
| — | the drawer scrim closes the drawer without navigating away | E2E | Not run yet | `frontend/e2e/responsive-layout.spec.ts` |

## Sprint 2: Sprint 2 - Background Indexing

### US-002: Extract, chunk and embed uploaded text in the background

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| — | Documents screen — indexing progress and failures > allows deleting a document that is still processing, and its poller stops for that id once deleted | Unit | Passed | `frontend/src/screens/Documents.test.tsx` |
| — | Documents screen — indexing progress and failures > cancelling the confirmation keeps the document and issues no DELETE request | Unit | Passed | `frontend/src/screens/Documents.test.tsx` |
| — | Documents screen — indexing progress and failures > deletes a document via the real API and removes it from the board | Unit | Passed | `frontend/src/screens/Documents.test.tsx` |
| — | Documents screen — indexing progress and failures > polls while a document is processing, updates aria-valuenow, and stops once terminal | Unit | Passed | `frontend/src/screens/Documents.test.tsx` |
| — | Documents screen — indexing progress and failures > renders a determinate progress bar from the server progress value with no sample data | Unit | Passed | `frontend/src/screens/Documents.test.tsx` |
| — | Documents screen — indexing progress and failures > renders a scanned-PDF failure reason the same way, with no chunk count | Unit | Passed | `frontend/src/screens/Documents.test.tsx` |
| — | Documents screen — indexing progress and failures > shows the server-supplied failure reason verbatim and no chunk count | Unit | Passed | `frontend/src/screens/Documents.test.tsx` |
| — | Documents screen — indexing progress and failures > states the deletion is permanent with no undo, requires no sign-in, and shows no 'deleted by' attribution | Unit | Passed | `frontend/src/screens/Documents.test.tsx` |
| — | Documents screen — indexing progress and failures > surfaces a non-blocking error when the DELETE request fails, leaving the document in place | Unit | Passed | `frontend/src/screens/Documents.test.tsx` |
| — | Documents screen — indexing progress and failures > surfaces upload rejections, including library-is-full, as error notices with the server's reason text | Unit | Passed | `frontend/src/screens/Documents.test.tsx` |

### US-006: Enforce a cap on total stored documents

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| — | test_cap_applies_within_the_same_batch_once_reached | Unit | Passed | `backend/tests/test_document_cap.py` |
| — | test_cap_rejected_file_creates_no_document_row_and_no_chunks | Unit | Passed | `backend/tests/test_document_cap.py` |
| — | test_cap_rejected_file_is_never_written_to_storage | Unit | Passed | `backend/tests/test_document_cap.py` |
| — | test_default_cap_applies_when_document_cap_env_unset | Unit | Passed | `backend/tests/test_document_cap.py` |
| — | test_deleting_a_document_at_cap_immediately_re_enables_uploading | Unit | Passed | `backend/tests/test_document_cap.py` |
| — | test_document_cap_function_reflects_env_default_and_override | Unit | Passed | `backend/tests/test_document_cap.py` |
| — | test_overridden_document_cap_env_value_is_honoured | Unit | Passed | `backend/tests/test_document_cap.py` |
| — | test_upload_rejected_with_library_full_reason_once_cap_reached | Unit | Passed | `backend/tests/test_document_cap.py` |

## Sprint 3: Sprint 3 - Document Lifecycle & Threads

### US-005: Delete a document and remove it from the index

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| — | test_delete_removes_document_row_object_and_chunks_and_omits_it_from_list | Unit | Passed | `backend/tests/test_document_delete.py` |
| — | test_delete_requires_no_auth_issues_no_undo_token_and_writes_no_actor_field | Unit | Passed | `backend/tests/test_document_delete.py` |
| — | test_delete_unknown_document_id_returns_404 | Unit | Passed | `backend/tests/test_document_delete.py` |
| — | test_deleted_documents_chunks_are_absent_from_the_whole_chunk_table | Unit | Passed | `backend/tests/test_document_delete.py` |
| — | test_deleting_a_processing_document_aborts_ingest_and_leaves_zero_chunks | Unit | Passed | `backend/tests/test_document_delete.py` |
| — | test_deleting_a_processing_document_between_batches_leaves_zero_chunks | Unit | Passed | `backend/tests/test_document_delete.py` |
| — | cancelling the confirmation leaves the document present and issues no DELETE | E2E | Not run yet | `frontend/e2e/document-delete.spec.ts` |
| — | confirming the deletion removes the row from the library and issues one DELETE | E2E | Not run yet | `frontend/e2e/document-delete.spec.ts` |
| — | the confirmation dialog warns deletion is permanent and cannot be undone | E2E | Not run yet | `frontend/e2e/document-delete.spec.ts` |

### US-014: Start, open and continue any thread

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| — | test_a_second_client_instance_over_the_same_database_reconstructs_the_thread | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_a_second_question_leaves_the_title_unchanged | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_a_very_long_first_question_yields_a_title_truncated_to_60_chars | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_create_thread_then_get_it_returns_an_empty_new_conversation | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_delete_returns_204_and_removes_all_messages_and_citations | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_delete_unknown_thread_id_returns_404 | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_first_question_sets_a_derived_title | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_get_unknown_thread_id_returns_404 | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_list_threads_is_identical_for_different_callers | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_list_threads_orders_by_last_active_at_descending | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_list_threads_returns_empty_list_when_there_are_none | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_no_thread_route_returns_401_or_403_for_an_unauthenticated_caller | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_rename_stores_and_returns_the_new_title_for_every_caller | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_rename_unknown_thread_id_returns_404 | Unit | Passed | `backend/tests/test_threads.py` |
| — | test_rename_with_empty_title_returns_422_and_leaves_previous_title_intact | Unit | Passed | `backend/tests/test_threads.py` |
| — | Chat screen — live threads API > blocks saving an empty title and keeps the previous title displayed | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > creates a new thread and posts the first message when sending from the empty composer state | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > expands a citation to show the excerpt via the keyboard | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > loads a thread via GET /threads/{id} and renders questions, answers and citations in order, with citations collapsed until expanded | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > offers no control to limit the search to particular documents | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > posts to an existing thread id when sending a follow-up question in a thread started by someone else | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > renames a thread inline and reflects the stored value after refetch | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > renders a Markdown answer and lists each distinct source once, even when the same source backs several chunks | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > renders assistant text progressively as token events arrive, then settles on the final persisted message | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > renders no sources block and no empty heading for an assistant answer with no citations | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > renders threads from GET /threads, most recently active first, each showing its title | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > restores the sidebar and the open thread from the server on reload, via the URL rather than localStorage | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > returns to the empty/new conversation state when deleting the currently open thread | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > shows a 'did not finish' note with a way to ask again for an incomplete assistant message, and keeps the composer usable | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > shows a loading state for the sidebar, then clears it once threads resolve | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > shows a no-documents-indexed message with a working link to Documents instead of an answer | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > shows a permanent-deletion warning, deletes via the API, and removes the thread from the sidebar | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > shows an empty state with a working new-conversation affordance when there are zero threads | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > shows an inline error, restores the failed question into the composer, and keeps earlier messages intact on a send failure | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > states the source document is no longer in the library when document_available is false | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | Chat screen — live threads API > surfaces a sidebar load error with a retry that succeeds | Unit | Passed | `frontend/src/screens/Chat.test.tsx` |
| — | returns the chat area to the empty state | E2E | Not run yet | `frontend/e2e/threads-sidebar.spec.ts` |
| — | shows an empty-state message and a working new-conversation action | E2E | Not run yet | `frontend/e2e/threads-sidebar.spec.ts` |
| — | shows its history and citations | E2E | Not run yet | `frontend/e2e/threads-sidebar.spec.ts` |
| — | updates the sidebar title, and an empty rename is rejected | E2E | Not run yet | `frontend/e2e/threads-sidebar.spec.ts` |
| — | with confirmation removes it from the sidebar | E2E | Not run yet | `frontend/e2e/threads-sidebar.spec.ts` |

## Sprint 5: Sprint 5 - Chat Experience & Protection

### US-011: Watch answers stream in token by token

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| — | test_citation_keeps_exact_chunk_text_and_deleted_document_serialises_unavailable | Unit | Passed | `backend/tests/test_chat_streaming.py` |
| — | test_completed_stream_persists_complete_message_and_deduplicated_citations | Unit | Passed | `backend/tests/test_chat_streaming.py` |
| — | test_follow_up_question_passes_prior_turns_to_generation_prompt | Unit | Passed | `backend/tests/test_chat_streaming.py` |
| — | test_interrupted_stream_persists_incomplete_message_and_thread_accepts_another_question | Unit | Passed | `backend/tests/test_chat_streaming.py` |
| — | test_long_thread_history_is_trimmed_before_the_generation_call_and_still_answers | Unit | Passed | `backend/tests/test_chat_streaming.py` |
| — | test_new_thread_question_carries_no_turns_from_another_thread | Unit | Passed | `backend/tests/test_chat_streaming.py` |
| — | test_post_message_streams_multiple_token_events_before_final | Unit | Passed | `backend/tests/test_chat_streaming.py` |
| — | answer text grows progressively and citations appear on completion | E2E | Not run yet | `frontend/e2e/chat-streaming.spec.ts` |
| — | expands to show excerpt, file name and page/section, collapses unchanged, and shows deleted-source wording | E2E | Not run yet | `frontend/e2e/chat-streaming.spec.ts` |
| — | shows the did-not-complete indication and allows asking again | E2E | Not run yet | `frontend/e2e/chat-streaming.spec.ts` |

### US-019: Rate limit chat and upload per IP

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| — | test_chat_limit_is_read_from_rate_limit_chat_per_min_env_var | Unit | Passed | `backend/tests/test_rate_limit.py` |
| — | test_chat_requests_succeed_again_after_the_limiter_window_elapses | Unit | Passed | `backend/tests/test_rate_limit.py` |
| — | test_different_client_ips_are_rate_limited_independently | Unit | Passed | `backend/tests/test_rate_limit.py` |
| — | test_exceeding_chat_limit_returns_429_and_never_invokes_generation_seam | Unit | Passed | `backend/tests/test_rate_limit.py` |
| — | test_exceeding_upload_limit_returns_429_and_persists_nothing_for_rejected_request | Unit | Passed | `backend/tests/test_rate_limit.py` |
| — | test_typical_chat_traffic_under_the_default_chat_limit_all_stay_200 | Unit | Passed | `backend/tests/test_rate_limit.py` |
| — | test_typical_upload_traffic_under_the_default_upload_limit_all_stay_200 | Unit | Passed | `backend/tests/test_rate_limit.py` |
| — | test_upload_limit_is_read_from_rate_limit_uploads_per_hour_env_var | Unit | Passed | `backend/tests/test_rate_limit.py` |
| — | test_upload_requests_succeed_again_after_the_limiter_window_elapses | Unit | Passed | `backend/tests/test_rate_limit.py` |

## Sprint 6: Sprint 6 - Launch Readiness

### US-022: Correct chat message bubble alignment

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| AC-071 | Chat message bubble alignment > [AC-071] renders user bubbles right-aligned and assistant bubbles left-aligned, each with a stable test hook | Unit | Passed | `frontend/src/screens/Chat.bubbles.test.tsx` |
| AC-072 | Chat message bubble alignment > [AC-072] keeps the streaming bubble left-aligned as it grows token by token | Unit | Passed | `frontend/src/screens/Chat.bubbles.test.tsx` |
| AC-073 | Chat message bubble alignment > [AC-073] wraps a long answer and long citation text inside the bubble's max-width without widening it | Unit | Passed | `frontend/src/screens/Chat.bubbles.test.tsx` |
| AC-075 | Chat message bubble alignment > [AC-075] renders a reloaded thread's full history with the same alignment as a newly sent message | Unit | Passed | `frontend/src/screens/Chat.bubbles.test.tsx` |
| — | every user bubble aligns right, every assistant bubble aligns left, and the two sides differ | E2E | Not run yet | `frontend/e2e/chat-bubble-alignment.spec.ts` |
| — | first and last bubbles (and everything between) match their role's alignment | E2E | Not run yet | `frontend/e2e/chat-bubble-alignment.spec.ts` |
| — | left edge is constant as tokens append and after the final event | E2E | Not run yet | `frontend/e2e/chat-bubble-alignment.spec.ts` |
| — | no document horizontal scrolling and both bubble sides stay fully visible | E2E | Not run yet | `frontend/e2e/chat-bubble-alignment.spec.ts` |
| — | no horizontal overflow of the bubble, and alignment holds after expanding citations | E2E | Not run yet | `frontend/e2e/chat-bubble-alignment.spec.ts` |

### US-020: Configure and run the app with a Gemini API key

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| AC-065, AC-069 | Setup screen — static operator documentation (AC-065..070) > contains no pricing, paywall UI, subscription or upgrade affordance (AC-069) | Unit | Passed | `frontend/src/screens/Setup.test.tsx` |
| AC-065, AC-066 | Setup screen — static operator documentation (AC-065..070) > describes the delivered stack's run and deploy instructions (AC-065/AC-066) | Unit | Passed | `frontend/src/screens/Setup.test.tsx` |
| AC-065 | Setup screen — static operator documentation (AC-065..070) > lists exactly the environment variables the backend reads, with documented defaults (AC-065) | Unit | Passed | `frontend/src/screens/Setup.test.tsx` |
| AC-065, AC-067 | Setup screen — static operator documentation (AC-065..070) > matches the backend's actual missing/invalid key messages, naming GEMINI_API_KEY (AC-067) | Unit | Passed | `frontend/src/screens/Setup.test.tsx` |
| AC-065, AC-068 | Setup screen — static operator documentation (AC-065..070) > never renders a key value and states the key is server-side only (AC-068) | Unit | Passed | `frontend/src/screens/Setup.test.tsx` |
| AC-065 | Setup screen — static operator documentation (AC-065..070) > renders without throwing and states it is static documentation, not a live status page | Unit | Passed | `frontend/src/screens/Setup.test.tsx` |
| AC-065, AC-070 | Setup screen — static operator documentation (AC-065..070) > states Gemini usage bills the operator's own Google account and the app bills no one (AC-070) | Unit | Passed | `frontend/src/screens/Setup.test.tsx` |

### US-023: Apply blue/purple accent color tokens across the app

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| — | --brand-primary and --brand-accent resolve to the new palette on the root element | E2E | Not run yet | `frontend/e2e/accent-color-tokens.spec.ts` |
| — | the Setup screen's footer 'Ask a question' link uses the accent token verbatim | E2E | Not run yet | `frontend/e2e/accent-color-tokens.spec.ts` |
| — | the Setup screen's footer 'Documents' link uses the accent token verbatim | E2E | Not run yet | `frontend/e2e/accent-color-tokens.spec.ts` |
| — | the active Setup-screen tab is highlighted with the new primary color, the inactive tabs are not | E2E | Not run yet | `frontend/e2e/accent-color-tokens.spec.ts` |
| — | the app background and corner-radius tokens are untouched by the accent change, across screens | E2E | Not run yet | `frontend/e2e/accent-color-tokens.spec.ts` |
| — | the chat composer's 'Send' button renders with the new primary color at its usual size | E2E | Not run yet | `frontend/e2e/accent-color-tokens.spec.ts` |
| — | the currently open thread in the sidebar is highlighted with the new blue/purple accent, not the old neutral gray | E2E | Not run yet | `frontend/e2e/accent-color-tokens.spec.ts` |
| — | the empty-state 'New conversation' button renders with the new primary color at its usual size | E2E | Not run yet | `frontend/e2e/accent-color-tokens.spec.ts` |

## Project setup

| Criteria | Test | Level | Result | File |
|---|---|---|---|---|
| — | test_accepted_upload_is_indexed_without_the_caller_ever_invoking_the_indexer | Unit | Passed | `backend/tests/test_background_indexing.py` |
| — | test_chat_endpoint_answers_normally_without_key_when_no_ready_documents | Unit | Passed | `backend/tests/test_gemini_config_error.py` |
| — | test_chat_endpoint_returns_structured_503_when_gemini_not_configured_and_docs_ready | Unit | Passed | `backend/tests/test_gemini_config_error.py` |
| — | test_embed_texts_not_configured_names_gemini_api_key | Unit | Passed | `backend/tests/test_gemini_config_error.py` |
| — | test_embed_texts_rejected_key_names_gemini_api_key_and_status | Unit | Passed | `backend/tests/test_gemini_config_error.py` |
| — | test_generate_answer_not_configured_names_gemini_api_key | Unit | Passed | `backend/tests/test_gemini_config_error.py` |
| — | test_generate_answer_rejected_key_names_gemini_api_key_and_status | Unit | Passed | `backend/tests/test_gemini_config_error.py` |
| — | test_rejected_key_error_never_includes_the_key_value | Unit | Passed | `backend/tests/test_gemini_config_error.py` |
| — | test_stream_answer_rejected_key_raises_immediately | Unit | Passed | `backend/tests/test_gemini_config_error.py` |
| — | test_api_key_never_appears_in_the_returned_answer | Unit | Passed | `backend/tests/test_generation.py` |
| — | test_gemini_failure_after_retries_raises_typed_service_error | Unit | Passed | `backend/tests/test_generation.py` |
| — | test_grounded_answer_returns_deduplicated_citations_from_retrieved_chunks_only | Unit | Passed | `backend/tests/test_generation.py` |
| — | test_missing_api_key_raises_typed_error | Unit | Passed | `backend/tests/test_generation.py` |
| — | test_no_ready_documents_returns_no_context_without_calling_gemini | Unit | Passed | `backend/tests/test_generation.py` |
| — | test_partial_coverage_answer_is_returned_grounded_with_citations | Unit | Passed | `backend/tests/test_generation.py` |
| — | test_question_not_covered_by_chunks_returns_not_found_with_no_citations | Unit | Passed | `backend/tests/test_generation.py` |
| — | test_zero_chunks_above_threshold_also_returns_no_context | Unit | Passed | `backend/tests/test_generation.py` |
| — | test_health_reports_each_service_as_configured_once_its_env_var_is_set | Unit | Passed | `backend/tests/test_health.py` |
| — | test_health_reports_ok | Unit | Passed | `backend/tests/test_health.py` |
| — | test_the_openapi_document_builds | Unit | Passed | `backend/tests/test_health.py` |
| — | test_chunk_fragments_keeps_each_fragment_independently_indexed_and_located | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_chunk_fragments_rejects_non_positive_size | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_chunk_fragments_splits_with_configured_size_and_overlap | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_embed_texts_raises_not_configured_when_key_missing | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_embed_texts_raises_service_error_after_exhausting_retries | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_embed_texts_retries_then_succeeds | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_extract_docx_groups_text_under_headings_with_file_name_prefix | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_extract_docx_with_no_headings_uses_file_name_as_location | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_extract_empty_file_returns_no_fragments | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_extract_md_returns_single_fragment_located_at_file_name | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_extract_pdf_blank_pages_yield_no_fragments | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_extract_txt_returns_single_fragment_located_at_file_name | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_extract_unsupported_extension_raises | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_ingest_document_embedding_failure_marks_failed_and_deletes_chunks | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_ingest_document_missing_gemini_key_fails_with_configuration_reason | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_ingest_document_no_extractable_text_fails_without_storing_chunks | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_ingest_document_progress_advances_across_batches_before_completion | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_ingest_document_success_stores_chunks_and_marks_ready | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_ingest_document_unknown_id_is_a_no_op | Unit | Passed | `backend/tests/test_ingestion.py` |
| — | test_chunks_below_threshold_are_discarded | Unit | Passed | `backend/tests/test_retrieval.py` |
| — | test_chunks_from_non_ready_documents_are_excluded | Unit | Passed | `backend/tests/test_retrieval.py` |
| — | test_no_ready_documents_returns_empty_context_without_calling_gemini | Unit | Passed | `backend/tests/test_retrieval.py` |
| — | test_only_processing_documents_counts_as_no_ready_documents | Unit | Passed | `backend/tests/test_retrieval.py` |
| — | test_ranks_chunks_by_similarity_across_all_ready_documents | Unit | Passed | `backend/tests/test_retrieval.py` |
| — | test_ready_documents_but_zero_chunks_above_threshold_yields_empty_chunks | Unit | Passed | `backend/tests/test_retrieval.py` |
| — | test_signature_has_no_per_document_or_per_thread_filter | Unit | Passed | `backend/tests/test_retrieval.py` |
| — | test_top_k_limits_the_number_of_chunks_returned | Unit | Passed | `backend/tests/test_retrieval.py` |
| — | App > renders without crashing and shows the first screen's nav link | Unit | Passed | `frontend/src/App.test.tsx` |
| — | apiFetch — the JSON request helper every other endpoint function is built on > falls back to an empty detail when the error response body is not JSON | Unit | Passed | `frontend/src/lib/api.test.ts` |
| — | apiFetch — the JSON request helper every other endpoint function is built on > parses a successful JSON response | Unit | Passed | `frontend/src/lib/api.test.ts` |
| — | apiFetch — the JSON request helper every other endpoint function is built on > resolves to undefined for a 204 No Content response | Unit | Passed | `frontend/src/lib/api.test.ts` |
| — | apiFetch — the JSON request helper every other endpoint function is built on > throws an ApiError carrying the status and the backend's detail text on failure | Unit | Passed | `frontend/src/lib/api.test.ts` |
| — | postMessage — SSE stream parsing against the real backend contract > calls onToken for each token event, in order, and resolves with the final event's payload | Unit | Passed | `frontend/src/lib/api.test.ts` |
| — | postMessage — SSE stream parsing against the real backend contract > reassembles an SSE frame split mid-JSON across two chunked reads | Unit | Passed | `frontend/src/lib/api.test.ts` |
| — | postMessage — SSE stream parsing against the real backend contract > rejects when the connection drops before a final event ever arrives | Unit | Passed | `frontend/src/lib/api.test.ts` |
| — | postMessage — SSE stream parsing against the real backend contract > rejects with an ApiError carrying the status and detail for a non-2xx response (e.g. rate limited) | Unit | Passed | `frontend/src/lib/api.test.ts` |
| — | postMessage — SSE stream parsing against the real backend contract > rejects with an ApiError isNoDocumentsIndexedError recognises when the final event reports message_id: null | Unit | Passed | `frontend/src/lib/api.test.ts` |
| — | postMessage — SSE stream parsing against the real backend contract > rejects with the backend's own detail text when the stream sends an error event | Unit | Passed | `frontend/src/lib/api.test.ts` |
| — | posting to an unknown thread id responds 404 | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | rejects an unsupported file type with the documented accepted/rejected shape | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | renames with a 200 {id,title} shape, and rejects an empty title with 422 | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | renaming an unknown thread id responds 404 | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | responds 200 with an array, and each item (if any) has the documented shape | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | responds 200 with an array, most recently active first | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | responds 200 with id, title and created_at, and the thread is then listed and loadable | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | responds 204, and the thread is unreachable and unlisted afterwards | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | responds 404 for a document id that does not exist | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | responds 404 for a thread id that does not exist | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | streams text/event-stream and ends with a persisted 'not found' reply when the shared library has no ready document | E2E | Not run yet | `frontend/e2e/api-contract.spec.ts` |
| — | a question sent from the empty composer creates a thread the backend can load independently | E2E | Not run yet | `frontend/e2e/chat-thread-persistence-integration.spec.ts` |
| — | the new title is readable from a fresh API call, not just from the page's own state | E2E | Not run yet | `frontend/e2e/chat-thread-persistence-integration.spec.ts` |
| — | the app loads | E2E | Not run yet | `frontend/e2e/example.spec.ts` |
<!-- sdlc:auto:end tests -->
