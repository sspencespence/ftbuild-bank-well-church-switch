# Research Plan: Data sources and running cost for a yearly UK church-banking figure (Bank Well)

## Metadata

| Field | Value |
|-------|-------|
| Date | 2026-10-28 |
| Topic | Bank Well church data sources + cost |
| Domain | MIXED: TECHNICAL (data sources, licensing) primary; MARKET (pricing); domain accounting (Charity SORP) |
| Complexity | MEDIUM-HIGH |
| Team Size | 5 researchers + lead synthesis |
| Sub-questions | 7 |
| Tasks | 7 |

---

## Research Question

Which public or licensable data sources can Bank Well (a small UK charity campaign, ~£50/yr budget) use to
build a yearly, repeatable estimate of (a) the % of UK churches banking with banks rated 5 by bank.green and
(b) the money churches hold in **current accounts** at banks not rated 5 — and what would the yearly run cost?

Context: existing pipeline in `~/hackathon/ftbuild-bank-well-church-switch` (HANDOVER.md): Charity Commission
for England & Wales register (31,691 churches) → accounts PDFs (LLM-read) + website sort-code crawl → bank →
rating; OSM building linking. ~3.9k churches have a verified bank. The pipeline sums "cash at bank and in hand";
the team asked for "current accounts" — a definition conflict this research must inform.

**Orchestration**: every claim carries a source URL + date checked (2026-10-28); claims are tagged
SOURCED or JUDGEMENT; licence/terms claims quote the publisher's own primary page.

---

## Research Question Decomposition

| ID | Sub-question | Domain | Parallel | Dependencies | Assigned To |
|----|-------------|--------|----------|--------------|-------------|
| SQ-1 | OSCR (Scotland) and CCNI (Northern Ireland) register downloads: URL, format, fields (esp. purpose/classification, income, accounts docs), licence, refresh cadence; can religious charities be filtered? | TECHNICAL | yes | NONE | Regulator Registers Analyst |
| SQ-2 | Church of England "A Church Near You" / CofE church lists: is a bulk list or API available, terms of use, robots.txt, scrapeability; counts | TECHNICAL | yes | NONE | Church Directory Analyst |
| SQ-3 | Other denomination / find-a-church directories (Methodist, Baptist Union, URC, Catholic dioceses, Evangelical Alliance, FIEC, Pentecostal/Elim/AoG, churches-near-me sites): APIs, data provenance, terms | TECHNICAL | yes | NONE | Church Directory Analyst |
| SQ-4 | UK address data: does OS AddressBase carry a place-of-worship classification code (exact code), licence terms (PSGA eligibility for charities?), and open alternatives (OS Open UPRN, OSM, ONS) that could locate churches | TECHNICAL | yes | NONE | Address Data Analyst |
| SQ-5 | Charity accounts disclosure: under Charities SORP (FRS 102) and receipts-and-payments accounts, can current-account balances be separated from "cash at bank and in hand"? How are CofE Parish Giving Scheme funds and diocesan/central-held funds reported? Is the Charity Commission register's financial data (Part B, income bands) usable? | DOMAIN (accounting) | yes | NONE | Charity Accounts Analyst |
| SQ-6 | Cost of a yearly incremental read of 2,000–8,000 accounts PDFs (avg ~15 pages): Anthropic API pricing (Haiku/Sonnet, Batch discount, PDF token cost), cheap alternatives (Gemini Flash, local OCR+regex, local VLM), vs a £50/yr cap | MARKET | yes | NONE | Cost Analyst |
| SQ-7 | Synthesis: recommended source stack, definition implications, cost envelope, open risks | SYNTHESIS | no | SQ-1..6 | Lead (main session) |

### Dependency Graph

```
SQ-1 ─┐
SQ-2 ─┤
SQ-3 ─┤
SQ-4 ─┼──► SQ-7 (synthesis, lead)
SQ-5 ─┤
SQ-6 ─┘
```

---

## Team Composition

Shared standards (included in every spawn prompt):
> Today is 2026-10-28. Use WebSearch/WebFetch. Every factual claim needs: source URL, date checked, and a
> tag SOURCED (quote or close paraphrase from that page) or JUDGEMENT (your inference, labelled). Licence /
> terms / pricing claims must come from the publisher's own primary page, quoted exactly. Confidence HIGH /
> MEDIUM / LOW with a reason. When sources disagree, give both. If you cannot verify something, write
> "UNVERIFIED" — never fill a gap from memory. Do not download bulk datasets or scrape; read pages/docs only.
> Return ≤900 words in the stated format.

### Regulator Registers Analyst
- **Focus**: Scottish (OSCR) and NI (CCNI) charity register bulk data.
- **Sub-questions**: SQ-1
- **Model**: sonnet
- **Output format**: per regulator — download URL, format, key fields, religious-filter option, accounts/financials available, licence (quoted), refresh cadence; then gaps.
- **Completion criteria**: both regulators covered; licence quoted from primary page or marked UNVERIFIED.

**Spawn prompt**: see RT-1 brief (as dispatched).

### Church Directory Analyst
- **Focus**: CofE A Church Near You and other denomination/find-a-church directories.
- **Sub-questions**: SQ-2, SQ-3
- **Model**: sonnet
- **Output format**: table — directory | owner | coverage count | bulk/API? | terms (quoted) | robots.txt | provenance | usable for Bank Well? (JUDGEMENT).
- **Completion criteria**: CofE + ≥6 other directories covered.

### Address Data Analyst
- **Focus**: AddressBase classification codes, PSGA/charity licensing, open alternatives.
- **Sub-questions**: SQ-4
- **Model**: sonnet
- **Output format**: classification code(s) quoted; licence options table; open alternatives table; can-a-small-charity-use-it verdict (JUDGEMENT).
- **Completion criteria**: place-of-worship code confirmed or marked UNVERIFIED; at least one open alternative assessed.

### Charity Accounts Analyst
- **Focus**: what accounts disclose about bank balances; Parish Giving Scheme; register financial data.
- **Sub-questions**: SQ-5
- **Model**: sonnet
- **Output format**: findings per question; a clear answer to "can current accounts be separated" with evidence.
- **Completion criteria**: SORP and R&P regimes both covered; PGS reporting answered or UNVERIFIED.

### Cost Analyst
- **Focus**: per-run cost of an incremental PDF read vs £50/yr.
- **Sub-questions**: SQ-6
- **Model**: sonnet
- **Output format**: pricing table (quoted, dated) + worked cost for 2k/5k/8k PDFs × 15 pages + cheapest viable option.
- **Completion criteria**: ≥3 options costed with arithmetic shown.

### Lead (main session)
- **Focus**: synthesis — SQ-7. **Model**: opus.

---

## Research Tasks

### Wave 1: Foundation (Parallel)

| ID | Title | Assignee | Type | Dependencies | Acceptance Criteria | Effort |
|----|-------|----------|------|-------------|-------------------|--------|
| RT-1 | OSCR + CCNI registers | Regulator Registers Analyst | RESEARCH | NONE | SQ-1 completion criteria | MED |
| RT-2 | CofE + denomination directories | Church Directory Analyst | RESEARCH | NONE | SQ-2/3 completion criteria | HIGH |
| RT-3 | Address data + classification | Address Data Analyst | RESEARCH | NONE | SQ-4 completion criteria | MED |
| RT-4 | Accounts disclosure / PGS | Charity Accounts Analyst | RESEARCH | NONE | SQ-5 completion criteria | MED |
| RT-5 | PDF-read cost envelope | Cost Analyst | RESEARCH | NONE | SQ-6 completion criteria | MED |

### Wave 2: Deep Analysis

| ID | Title | Assignee | Type | Dependencies | Acceptance Criteria | Effort |
|----|-------|----------|------|-------------|-------------------|--------|
| RT-6 | Verify load-bearing claims (licences, codes, prices) by spot-opening cited URLs | Lead | REVIEW | RT-1..5 | each load-bearing claim reopened; failures dropped or marked | LOW |

### Wave 3: Synthesis

| ID | Title | Assignee | Type | Dependencies | Acceptance Criteria | Effort |
|----|-------|----------|------|-------------|-------------------|--------|
| RT-7 | Source stack + definitions + cost recommendation | Lead | SYNTHESIS | RT-6 | answers the research question with cited evidence | MED |

### Cross-Cutting Concerns

- **Citations**: URL + "checked 2026-10-28"; SOURCED / JUDGEMENT tag per claim.
- **Confidence levels**: HIGH / MEDIUM / LOW with rationale.
- **Contradictions**: both positions with evidence.
- **Scope boundaries**: no downloading or scraping; stop at what a small charity could legally and cheaply use.

---

## Team Orchestration Guide

### Prerequisites
Agent teams not used: executed via the manual alternative (parallel Agent subagents, `web-researcher` type).

### Execution Steps
1. Dispatch RT-1..RT-5 in one message (parallel).
2. Lead runs RT-6 (spot-verify) on return.
3. Lead writes RT-7 synthesis back to the user.

### Display Mode
Background subagents; lead is notified on completion.

### Communication Patterns
No inter-researcher messaging; contradictions resolved by the lead in RT-6.

### Plan Approval
- [x] Team composition matches the research domain
- [x] Spawn prompts are self-contained
- [x] Task dependencies are correct
- [x] Acceptance criteria are measurable

---

## Acceptance Criteria

- [ ] Every sub-question (SQ-*) investigated and answered
- [ ] Every research task (RT-*) meets its acceptance criteria
- [ ] Findings cited with sources and confidence levels
- [ ] Contradictions documented
- [ ] Synthesis integrates findings
- [ ] Original question answered with evidence

---

## Output Format: Final Report Structure

1. Executive Summary 2. Key Findings 3. Detailed Analysis (per SQ) 4. Comparative Matrix (sources) 5. Recommendations 6. Sources (URL + date) 7. Appendix
