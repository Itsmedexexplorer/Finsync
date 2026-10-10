# VERITY BACKEND ↔ FRONTEND CONTRACT MATRIX
**Integration Audit I1 — Full System Contract Inventory & Data Flow Map**

---

## 1. Global Shell & Readiness
| Workspace | Frontend Function | API Endpoint | HTTP Method | Request Contract | Response Contract | Fields Consumed | Backend Source | State Dependencies | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Shell** | `checkReady()` | `/ready` | `GET` | None | `{ "status": "READY", "subsystems": {...} }` | `status`, `subsystems` | `backend.api.routes:ready` | None | **YES** |
| **Shell** | `loadDemoCases()` | `/api/v1/demo-cases` | `GET` | None | `Array<{ id, name, description, ... }>` | `id`, `name`, `description` | `backend.api.routes:list_demo_cases` | None | **YES** |

---

## 2. Command Center Workspace
| Workspace | Frontend Function | API Endpoint | HTTP Method | Request Contract | Response Contract | Fields Consumed | Backend Source | State Dependencies | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Command Center** | `loadPortfolioMetrics()` | `/api/v1/portfolio/summary` | `GET` | None | `PortfolioSummaryResponse` | `total_cases`, `open_cases`, `needs_attention`, `resolved_cases`, `sla_breaches`, `status_distribution` | `backend.api.routes:get_portfolio_summary` | None | **YES** |
| **Command Center** | `loadPortfolioMetrics()` | `/api/v1/portfolio/exposure` | `GET` | None | `PortfolioExposureResponse` | `total_exposure_amount`, `high_risk_exposure_amount`, `exposure_by_entity`, `high_risk_entities` | `backend.api.routes:get_portfolio_exposure` | None | **YES** |
| **Command Center** | `loadWorkloadMetrics()` | `/api/v1/portfolio/workload` | `GET` | None | `PortfolioWorkloadResponse` | `total_assigned_cases`, `unassigned_cases`, `workload_by_reviewer`, `overloaded_reviewers` | `backend.api.routes:get_portfolio_workload` | None | **YES** |
| **Command Center** | `loadCasesTable()` | `/api/v1/portfolio/review-queue` | `GET` | `?priority=...` (optional) | `Array<PortfolioCaseItem>` | `case_id`, `status`, `priority`, `risk_level`, `assigned_to`, `sla_deadline` | `backend.api.routes:get_portfolio_review_queue` | None | **YES** |

---

## 3. Case Investigation Workspace
| Workspace | Frontend Function | API Endpoint | HTTP Method | Request Contract | Response Contract | Fields Consumed | Backend Source | State Dependencies | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Case Investigation**| `inspectTriageCase()` | `/api/v1/cases/{caseId}` | `GET` | None | `CaseStateResponse` | `case_id`, `status`, `confidence`, `summary`, `reconciliation_id`, `expected_amount`, `matched_amount`, `outstanding_amount`, `counterparty`, `discrepancies` | `backend.api.routes:get_case` | Active Case Selection | **YES** |
| **Case Investigation**| `inspectTriageCase()` | `/api/v1/cases/{caseId}/report` | `GET` (fallback) | None | `TruthReportResponse` | `case_id`, `status`, `confidence_score`, `summary_text`, `truth_proof` | `backend.api.routes:get_case_report` | Active Case Selection | **YES** |
| **Case Investigation**| `handleManualUpload()` | `/api/v1/cases/files` | `POST` | `multipart/form-data: files` | `CaseStateResponse` | `case_id`, `status`, `evidence_count`, `claims` | `backend.api.routes:submit_files_evidence` | File Input | **YES** |
| **Case Investigation**| `handleManualUpload()` | `/api/v1/cases/text` | `POST` | `JSON: { text: "..." }` | `CaseStateResponse` | `case_id`, `status`, `claims` | `backend.api.routes:submit_text_evidence` | Text Input | **YES** |
| **Case Investigation**| `handleManualUpload()` | `/api/v1/cases` | `POST` | `JSON: CaseSubmission` | `CaseStateResponse` | `case_id`, `status` | `backend.api.routes:submit_structured_case`| JSON Input | **YES** |

---

## 4. Evidence Workspace
| Workspace | Frontend Function | API Endpoint | HTTP Method | Request Contract | Response Contract | Fields Consumed | Backend Source | State Dependencies | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Evidence** | `renderEvidenceGrid()` | `/api/v1/cases/{caseId}` | `GET` (via active state) | None | `CaseStateResponse` | `evidence_items`: `[ { id, filename, source_type, sha256_hash, extracted_claims, verification_status } ]` | `backend.api.routes:get_case` | `currentCaseResult` | **YES** |

---

## 5. Counterparty Memory & Dossier Workspace
| Workspace | Frontend Function | API Endpoint | HTTP Method | Request Contract | Response Contract | Fields Consumed | Backend Source | State Dependencies | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Counterparty** | `loadCounterpartyData()` | `/api/v1/cases/{caseId}/intelligence-profile` | `GET` | None | `IntelligenceProfileResponse` | `canonical_entity`, `historical_case_count`, `lifetime_exposure`, `disputed_exposure`, `risk_level`, `historical_risk_signals`, `recurring_discrepancies`, `reference_reuse_history`, `correlated_cases` | `backend.api.routes:get_case_intelligence_profile` | `caseId` | **YES** |

---

## 6. AI Finance Controller Workspace
| Workspace | Frontend Function | API Endpoint | HTTP Method | Request Contract | Response Contract | Fields Consumed | Backend Source | State Dependencies | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Controller** | `loadControllerWorkspaceData()` | `/api/v1/cases/{caseId}/controller/brief` | `GET` | None | `ControllerBriefResponse` | `case_id`, `controller_status`, `risk_rating`, `recommended_decision`, `human_review_required`, `brief_text`, `decision_factors`, `action_directives`, `grounding_evidence_ids` | `backend.api.routes:get_controller_brief` | `caseId` | **YES** |
| **Controller** | `askControllerAssistant()` | `/api/v1/cases/{caseId}/controller/explain` | `POST` | `{ "query": "..." }` | `ControllerExplainResponse` | `query`, `answer`, `grounded_case_id`, `deterministic_basis`, `evidence_references`, `policy_clauses` | `backend.api.routes:explain_controller_decision` | Active Case + User Query | **YES** |

---

## 7. Human Review & Audit Chain Workspace
| Workspace | Frontend Function | API Endpoint | HTTP Method | Request Contract | Response Contract | Fields Consumed | Backend Source | State Dependencies | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Review** | `loadReviewWorkspaceData()` | `/api/v1/cases/{caseId}/review` | `GET` | None | `ReviewRecordResponse` | `case_id`, `review_status`, `assigned_to`, `evidence_checklist`, `action_items`, `reviewer_notes`, `final_decision`, `is_locked` | `backend.api.routes:get_case_review` | `caseId` | **YES** |
| **Review** | `startHumanReview()` | `/api/v1/cases/{caseId}/review/start` | `POST` | `{ "reviewer": "..." }` | `ReviewRecordResponse` | `review_status: "IN_PROGRESS"`, `assigned_to` | `backend.api.routes:start_case_review` | Active Review | **YES** |
| **Review** | `submitReviewerNote()` | `/api/v1/cases/{caseId}/review/note` | `POST` | `{ "author": "...", "text": "..." }` | `ReviewRecordResponse` | `reviewer_notes` | `backend.api.routes:add_review_note` | Active Review | **YES** |
| **Review** | `inspectEvidenceItem()` | `/api/v1/cases/{caseId}/review/evidence/{evidenceId}` | `POST` | None | `ReviewRecordResponse` | `evidence_checklist` (inspected status) | `backend.api.routes:inspect_review_evidence` | Active Review | **YES** |
| **Review** | `completeChecklistAction()` | `/api/v1/cases/{caseId}/review/action/{actionId}/complete` | `POST` | None | `ReviewRecordResponse` | `action_items` (completed status) | `backend.api.routes:complete_review_action` | Active Review | **YES** |
| **Review** | `submitReviewDecision()` | `/api/v1/cases/{caseId}/review/decision` | `POST` | `{ "decision": "...", "rationale": "...", "reviewer": "..." }` | `ReviewRecordResponse` | `final_decision`, `review_status: "DECIDED"` | `backend.api.routes:submit_review_decision` | Active Review | **YES** |
| **Review** | `resolveReview()` | `/api/v1/cases/{caseId}/review/resolve` | `POST` | None | `ReviewRecordResponse` | `review_status: "RESOLVED"`, `is_locked: true` | `backend.api.routes:resolve_case_review` | Active Review | **YES** |
| **Review** | `closeReview()` | `/api/v1/cases/{caseId}/review/close` | `POST` | None | `ReviewRecordResponse` | `review_status: "CLOSED"`, `is_locked: true` | `backend.api.routes:close_case_review` | Active Review | **YES** |
| **Review** | `loadAuditChainData()` | `/api/v1/cases/{caseId}/review/audit` | `GET` | None | `AuditChainResponse` | `events`: `[ { event_id, event_type, actor, timestamp, payload_hash, prev_hash } ]` | `backend.api.routes:get_case_audit_chain` | `caseId` | **YES** |
| **Review** | `verifyAuditChainIntegrity()`| `/api/v1/cases/{caseId}/review/audit/verify`| `GET` | None | `AuditVerifyResponse` | `is_valid`, `verified_events_count`, `merkle_root_hash`, `tamper_detected` | `backend.api.routes:verify_case_audit_chain`| `caseId` | **YES** |
| **Review** | `assignReviewer()` | `/api/v1/portfolio/cases/{caseId}/assign` | `POST` | `{ "reviewer_id": "..." }` | `{ "status": "ASSIGNED", ... }` | `assigned_to`, `case_id` | `backend.api.routes:assign_portfolio_case` | Portfolio Case Selection | **YES** |

---

## 8. Remediation & Action Workspace
| Workspace | Frontend Function | API Endpoint | HTTP Method | Request Contract | Response Contract | Fields Consumed | Backend Source | State Dependencies | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Remediation** | `loadRemediationData()` | `/api/v1/cases/{caseId}/actions` | `GET` | None | `Array<RemediationAction>` | `action_id`, `action_type`, `status`, `target_party`, `amount`, `title`, `description`, `created_at` | `backend.api.routes:get_case_actions` | `caseId` | **YES** |
| **Remediation** | `loadRemediationData()` | `/api/v1/cases/{caseId}/journal-voucher` | `GET` | None | `JournalVoucherResponse` | `voucher_id`, `is_balanced`, `total_debits`, `total_credits`, `lines`, `deterministic_basis`, `provenance_hash` | `backend.api.routes:get_case_journal_voucher` | `caseId` | **YES** |
| **Remediation** | `proposeRemediationAction()`| `/api/v1/cases/{caseId}/actions/propose` | `POST` | `{ "action_type": "...", "description": "..." }` | `RemediationAction` | `action_id`, `status: "PENDING_APPROVAL"`, `title`, `description` | `backend.api.routes:propose_case_action` | Active Case | **YES** |
| **Remediation** | `approveRemediationAction()`| `/api/v1/cases/{caseId}/actions/{actionId}/approve` | `POST` | `{ "approver": "..." }` | `RemediationAction` | `status: "APPROVED"`, `approved_by` | `backend.api.routes:approve_case_action` | Action Selection | **YES** |
| **Remediation** | `rejectRemediationAction()` | `/api/v1/cases/{caseId}/actions/{actionId}/reject` | `POST` | `{ "reason": "..." }` | `RemediationAction` | `status: "REJECTED"` | `backend.api.routes:reject_case_action` | Action Selection | **YES** |
| **Remediation** | `exportJournalVoucher()` | `/api/v1/cases/{caseId}/journal-voucher/export` | `POST` | None | `JournalExportResponse` | `status: "EXPORTED"`, `voucher`, `export_format: "JSON"`, `audit_recorded: true` | `backend.api.routes:export_case_journal_voucher`| Balanced Voucher State | **YES** |

---

## 9. Audit & Provenance Workspace
| Workspace | Frontend Function | API Endpoint | HTTP Method | Request Contract | Response Contract | Fields Consumed | Backend Source | State Dependencies | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Audit** | `renderProvenanceView()` | `/api/v1/cases/{caseId}/provenance` | `GET` (via Case State / Report) | None | `ProvenanceResponse` | `reconciliation_id`, `evidence_hashes`, `extracted_claims`, `matched_transactions`, `algorithm: "SHA-256"` | `backend.api.routes:get_case_provenance` | Active Case Selection | **YES** |
| **Audit** | `renderReportView()` | `/api/v1/cases/{caseId}/report` | `GET` (via Case State / Report) | None | `TruthReportResponse` | `case_id`, `status`, `reconciliation_result`, `raw_json` | `backend.api.routes:get_case_report` | Active Case Selection | **YES** |

---

## 10. Explicit Golden Demo Benchmarks (User-Triggered Only)
| Workspace | Frontend Function | API Endpoint | HTTP Method | Trigger Constraint | Backend Source | State Guard | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Golden Demo** | `runDemoCase()` | `/api/v1/demo-cases/{caseId}/run` | `POST` | **EXPLICIT USER CLICK ON DEMO CARD ONLY** | `backend.api.routes:run_demo_case` | Never triggered on navigation or case click | **YES** |
| **Golden Demo** | `runCorrelatedSignalsDemo()`| `/api/v1/demo-cases/DAY18-02-REPEAT-COUNTERPARTY/run` | `POST` | **EXPLICIT USER CLICK ON CORRELATED DEMO ONLY** | `backend.api.routes:run_demo_case` | Never triggered on navigation | **YES** |
