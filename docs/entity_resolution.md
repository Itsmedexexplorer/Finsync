# VERITY Entity Resolution Subsystem

**Day 4 Milestone: Deterministic Multi-Signal Entity Resolution**  
*Razorpay AI Buildathon 2026 | Track: AI Finance Controller*

---

## 1. Core Principles & False-Merge Philosophy

Entity Resolution determines which real-world legal entity or individual an extracted `Claim` counterparty hint refers to.

### 🔒 Core Invariant & Philosophy
$$\mathbf{A\ wrong\ identity\ is\ worse\ than\ an\ unresolved\ identity.}$$

1. **Zero False Merges**:
   - Similar names without distinguishing identifiers (e.g. *"Rahul"* with known entities *"Rahul Kumar"* and *"Rahul Sharma"*) will strictly produce `AMBIGUOUS`, **never** an arbitrary silent merge.
2. **Conflict Preservation**:
   - If signals contradict each other (e.g. phone matches Entity A, but UPI VPA matches another party), the system records `CONFLICTING`.
3. **Amounts & Dates are NOT Identity Proof**:
   - Two entities receiving ₹20,000 on the same date remain strictly separate entities. Transaction amounts and ledger dates are never treated as identity proofs.
4. **Traceable Lineage**:
   - $\text{Evidence} \to \text{Claim} \to \text{Entity Resolution} \to \text{Candidate(s)}$.

---

## 2. Multi-Signal Scoring Matrix

VERITY employs a transparent, explainable scoring engine combining strong official identifiers, payment rails, and normalized names:

| Signal Type | Weight | Description & Examples |
|---|---|---|
| `EXACT_TAX_ID` | `1.00` | Exact 15-character GSTIN or 10-character PAN match. |
| `EXACT_UPI_VPA` | `0.98` | Exact match on registered Virtual Payment Address (`user@okhdfcbank`). |
| `EXACT_PHONE` | `0.95` | Exact match on normalized 10-digit Indian mobile number (`+919876543210`). |
| `EXACT_CANONICAL_NAME` | `0.95` | Exact match on normalized primary name (`"Rahul Kumar"`). |
| `EXACT_ALIAS` | `0.92` | Exact match on registered trade alias (`"M/s Shree Electronics"`). |
| `BUSINESS_NAME_VARIATION` | `0.85` | Match on core business tokens omitting legal corporate forms (`"Pvt Ltd"`, `"LLP"`). |
| `INITIALS_MATCH` | `0.65` | Initial match (`"R. Sharma"` $\leftrightarrow$ `"Rahul Sharma"`). |
| `SUBSET_NAME_MATCH` | `0.55` | Partial token match (`"Rahul"` $\leftrightarrow$ `"Rahul Kumar"`). |
| `FUZZY_NAME_SIMILARITY` | `0.50` | Jaro-Winkler / Levenshtein ratio $\ge 0.85$. |

---

## 3. Resolution Statuses

```python
class EntityResolutionStatus(str, Enum):
    CONFIRMED = "CONFIRMED"     # High-confidence match on strong identifier or combined signals with 0 conflicts
    PROBABLE = "PROBABLE"       # Probable match on exact alias, full name, or unique initials without conflicts
    AMBIGUOUS = "AMBIGUOUS"     # Multiple candidates matched with close scores (e.g. 'Rahul'). NEVER merged!
    CONFLICTING = "CONFLICTING" # Conflicting signals detected (e.g. matching phone + conflicting UPI VPA)
    UNRESOLVED = "UNRESOLVED"   # No matching candidate found or insufficient hints provided
```

---

## 4. Normalization Engine

`EntityNormalizer` prepares identifiers for fair deterministic comparison without altering underlying semantics:

- **Names**: Lowercase, removes punctuation, strips common prefixes (`M/s`, `Dr.`, `Shri`) and honorifics (`bhai`, `ji`).
- **Phones**: Strips spaces and formatting; standardizes `+91`, `91`, and `0` prefixes to canonical 10-digit format.
- **UPI VPAs**: Lowercase, whitespace-stripped, format-validated (`handle@bank`).
- **GSTIN & PAN**: Alphanumeric uppercase formatting.

---

## 5. API Usage Examples

```python
from backend.domain.entity import Entity, EntityType
from backend.domain.claim import Claim, ClaimType
from backend.entity_resolution import EntityRegistry, EntityResolutionService

# 1. Initialize Registry with known entities
registry = EntityRegistry([
    Entity(
        id="ENT-001",
        canonical_name="Rahul Kumar",
        entity_type=EntityType.INDIVIDUAL,
        pan="ABCDE1234F",
        upi_ids=["rahulkumar@ybl"],
        phone_numbers=["+919876543210"],
    ),
    Entity(
        id="ENT-002",
        canonical_name="Rahul Sharma",
        entity_type=EntityType.INDIVIDUAL,
        upi_ids=["rahul.sharma@okhdfcbank"],
        phone_numbers=["+919811022334"],
    ),
])

service = EntityResolutionService(registry=registry)

# 2. Resolve Unambiguous Claim (Exact UPI VPA)
claim1 = Claim(
    id="CLM-01",
    evidence_id="EVID-01",
    claim_type=ClaimType.PAYMENT_RECEIVED,
    claimed_amount=20000.0,
    counterparty_hint="rahulkumar@ybl",
)
res1 = service.resolve_claim(claim1)
print(f"Status: {res1.status.value}, Entity: {res1.selected_entity_id}")
# Output: Status: CONFIRMED, Entity: ENT-001

# 3. Resolve Ambiguous Name (Preserves Ambiguity)
claim2 = Claim(
    id="CLM-02",
    evidence_id="EVID-02",
    claim_type=ClaimType.PAYMENT_RECEIVED,
    claimed_amount=20000.0,
    counterparty_hint="Rahul",
)
res2 = service.resolve_claim(claim2)
print(f"Status: {res2.status.value}, Entity: {res2.selected_entity_id}")
# Output: Status: AMBIGUOUS, Entity: None (Human review requested)
```
