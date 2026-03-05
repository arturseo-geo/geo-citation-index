# AGENTS.md — Engineering Non-Negotiables

This document defines hard rules for anyone (human or AI agent) modifying
scoring, extraction, or report generation logic.

**Read `knowledge/failure_registry.yml` before touching any of these areas.**

---

## Brand Extraction

1. Rule pass must use word-boundary regex — no plain substring matching (FAIL-002)
2. Matched brand IDs must be deduplicated per RunResult — no alias double-counting (FAIL-001)
3. Dictionary terms must be sorted by length descending before iteration (FAIL-003)
4. LLM pass must only run when rule pass finds < MIN_BRANDS_RULE_PASS brands (FAIL-007)
5. New brands from LLM pass start as `is_verified=False` — never appear in public index until manually verified

## Citation Scoring

1. Absence from a platform = score of 0.0, never NULL — absence is valid data (FAIL-005)
2. Normalise within platform × vertical × run only — never compare raw scores cross-vertical (FAIL-006)
3. `classify_archetype()` must not be called when `run.gap_analysis_valid = False` (FAIL-004)
4. `bias_flag=True` queries must be excluded from BrandScore aggregation used for archetype (FAIL-008)
5. Archetype threshold values are not public — `archetype_signals` stored in CitationIndex must not include raw threshold values

## Content Generation

1. `generate_monthly_report()` must handle first-run context (empty deltas, empty archetype_changes) without producing broken output (FAIL-009)
2. Prompts must explicitly signal `is_baseline=True` context when applicable
3. All brand names and scores in generated content must come from real run data — never hallucinated

## Report Integrity

1. CitationIndex rows for unverified brands (`is_verified=False`) must never appear in JSON export
2. Archetype classification must not be written unless `gap_analysis_valid = True` on the run
3. `archetype_threshold_version` must be stored on every ArchetypeSnapshot and QueryRun so historical data remains interpretable after threshold changes

## Never Do

- Never compute archetypes from a single platform's data
- Never publish LLM-extracted brands to the public index without manual verification
- Never compare citation scores across verticals using raw (un-normalised) values
- Never remove the `bias_flag` check from scoring aggregation
- Never change `ARCHETYPE_THRESHOLD_VERSION` without bumping the version string in `app/core/config.py`
