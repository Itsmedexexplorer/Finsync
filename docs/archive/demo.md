# VERITY — Golden Demo & 3–5 Minute Judge Walkthrough Guide

**Project:** VERITY — "Financial Truth, Reconstructed"  
**Hackathon:** Razorpay AI Buildathon 2026  
**Track:** AI Finance Controller  
**Version:** Day 20 Golden Release  

---

## 🎯 Executive Pitch (30 Seconds)

> *"Indian businesses lose billions to messy, fragmented financial records — WhatsApp promises in Hinglish, scanned invoices, bank advice PDFs, and duplicate UTR claims across accounts. LLMs hallucinate numbers if asked to do accounting. Traditional ERPs choke on messy text.*
>
> *VERITY bridges this gap with an architectural breakthrough: **AI extracts candidate claims from messy multimodal evidence, but strictly deterministic engines establish financial truth with zero hallucination.** Cross-case counterparty memory detects fraud and reference reuse across cases, while the AI Finance Controller proposes fact-grounded remediation requiring explicit human-in-the-loop approval."*

---

## 🧭 Live Demo Click Sequence (3–5 Minutes)

### Step 1: Open the Controller Command Center
- Open `http://localhost:8000`.
- The top header confirms **Engine Ready** and **Storage: CONNECTED**.
- The primary default view is the **`🎯 Command Center (Golden Demo)`** featuring the **7-Scene Narrative**.

---

### Step 2: Hero Scenario — Click `[ HERO DEMO-05: Counterparty UTR Reuse ]`
*Demonstrates the full 7-scene journey and the "Wait, that's clever!" moment.*

#### **Scene 1: Messy Heterogeneous Evidence**
- **Show**: 2 evidence items ingested — an invoice from *Creative Minds Studio* (₹45,000) and a Bank Statement citing `UTR-CMS-002`.
- **Key Talking Point**: *"VERITY ingests messy multimodal evidence, assigns cryptographic SHA-256 hashes, and extracts candidate claims without mutating raw records."*

#### **Scene 2: AI Candidate Extraction vs. Deterministic Financial Truth**
- **Show the side-by-side split**:
  - **Left (🤖 AI Extraction)**: Candidate claims parsed by Gemini VLM / deterministic extractors with confidence scores. Sub-label clearly states: *"Provisional Candidate Hypotheses"*.
  - **Right (⚖️ Deterministic Truth)**: Mathematical status `CONFIRMED`, Expected: ₹45,000, Matched: ₹45,000, Outstanding: ₹0.00 with 100% mathematical certainty.
- **Key Talking Point**: *"Notice the strict architectural separation. AI extracts candidate claims; deterministic reconciliation math establishes financial truth."*

#### **Scene 3: Institutional Counterparty Memory ("Wait, that's clever!")**
- **Show**: Glowing Red Alert Box:
  `⚠️ HISTORICAL REFERENCE REUSE DETECTED: Bank Reference UTR-CMS-002 was already settled in historical case DAY18-02-REPEAT-COUNTERPARTY.`
- **Show**: Counterparty profile displays *Creative Minds Studio*, lifetime settled volume ₹1,35,000, and Historical Risk Rating: **HIGH**.
- **Key Talking Point**: *"Here is the breakthrough: Intra-case reconciliation is mathematically `CONFIRMED`, but our Cross-Case Intelligence layer remembers previous cases and detects that this exact bank UTR was already claimed. Financial Truth is untouched, but Historical Risk is immediately flagged as HIGH."*

#### **Scene 4: AI Finance Controller Decision Brief**
- **Show**: Controller Risk Level: `HIGH` (Reference Reuse Alert), Directive: `REVIEW_CASE & REQUEST_BANK_VERIFICATION`.
- **Key Talking Point**: *"The controller does not blindly approve or send automated emails. It generates an evidence-grounded brief recommending manual review."*

#### **Scene 5 & 6: Human Review & Safe Human-Gated Remediation**
- **Show**: Proposed Remediation Draft: `Missing Evidence Request` to *Creative Minds Studio*.
- **Show**: Action Status is visibly **`[ PENDING APPROVAL ]`**.
- **Click**: `[ ✓ Approve Action ]` button.
- **Show**: Action status updates to `✓ APPROVED by controller_ui`, and the draft journal voucher updates with balanced debits and credits (`DR Accounts Payable ₹45,000 / CR Bank Clearing ₹45,000 (BALANCED)`).
- **Key Talking Point**: *"No external dispatch ever occurs autonomously. Consequential financial actions require explicit human controller approval."*

#### **Scene 7: Cryptographic SHA-256 Audit Provenance**
- **Show**: The verified audit hash chain displaying every stage: Raw Evidence Ingestion $\to$ Deterministic Reconciliation $\to$ Controller Risk $\to$ Human Approval.
- **Key Talking Point**: *"Every step is cryptographically linked in an append-only SHA-256 audit chain. Any database tampering is mathematically detected."*

---

### Step 3: Quick Scenarios (1 Minute)
Click through the remaining scenario buttons to prove versatility:

1. **`DEMO-01: Clean 1:1 Settlement`**
   - Click `[ DEMO-01 ]` $\to$ Shows ₹35,000 clean match $\to$ `CONFIRMED` $\to$ Straight-through processing with balanced 2-line draft journal.
2. **`DEMO-02: Partial Settlement`**
   - Click `[ DEMO-02 ]` $\to$ Shows ₹12,000 paid on ₹20,000 invoice $\to$ `PARTIALLY_SETTLED` (₹8,000 outstanding) $\to$ Generates grounded Payment Follow-Up reminder.
3. **`DEMO-03: Amount Contradiction`**
   - Click `[ DEMO-03 ]` $\to$ Shows ₹18,000 bank credit vs ₹20,000 invoice claim $\to$ `CONTRADICTED` $\to$ Proposes grounded Vendor Dispute Notice citing ₹2,000 shortfall.
4. **`DEMO-04: Messy Multimodal Evidence`**
   - Click `[ DEMO-04 ]` $\to$ Shows messy Hinglish WhatsApp chat (`"kal maine 50k bhej diye..."`) + scanned invoice $\to$ Extracted and reconciled seamlessly.

---

### Step 4: Show Deep-Dive Operations Panels (30 Seconds)
Click into deep-dive tabs to demonstrate enterprise readiness:
- **`📊 Case Portfolio`**: Real-time SLA countdowns, priority scoring, reviewer workload balancing, and exposure analytics.
- **`🏛️ Counterparty Memory`**: Search counterparties, lifetime exposure, recurring discrepancy patterns, and multi-case relationship graphs.
- **`👤 Human Review`**: Non-destructive review investigation workspace with tamper-evident audit log.

---

## 🛡️ Critical Architectural Invariants for Judges

| Invariant | How VERITY Enforces It |
|---|---|
| **Zero AI Hallucination** | Financial numbers and reconciliation verdicts are computed exclusively by deterministic Python engines, not LLMs. |
| **Strict AI / Truth Separation** | Extraction outputs candidate claims; reconciliation computes mathematical truth. |
| **Zero Autonomous Dispatch** | Remediation actions always begin in `PENDING_APPROVAL` and require explicit human sign-off. |
| **Double-Entry Balance** | Every draft journal voucher strictly enforces $\sum \text{Debits} = \sum \text{Credits}$ ($\text{len} \ge 2$) and is marked as `DRAFT`. |
| **Cross-Case Isolation** | Institutional memory queries historical patterns without mutating intra-case arithmetic. |
| **Tamper-Evident Audit** | Every action and state transition is hashed in an append-only SHA-256 hash chain. |

---

## 🚫 What NOT to Demonstrate

1. Do NOT claim that AI calculates debit/credit arithmetic (explain that AI extracts candidate text while deterministic engines compute accounting truth).
2. Do NOT claim that VERITY autonomously sends live emails/SMS (emphasize that VERITY is a human-in-the-loop controller).
3. Do NOT claim the draft journal is an automatic direct post to ERP (emphasize it is a grounded draft awaiting controller account mapping).
