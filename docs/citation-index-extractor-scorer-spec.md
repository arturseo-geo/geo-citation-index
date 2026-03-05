# GEO Citation Index — Brand Extractor & Citation Scorer Spec

Status: Draft
Author: AJ / The GEO Lab
Last updated: 2026-03-05
Primary files: `app/core/brand_extractor.py`, `app/core/citation_scorer.py`
Depends on: `app/models/db.py`, `app/core/config.py`

---

## Overview

Two distinct modules with a clear boundary:

**`brand_extractor.py`** — Reads `RunResult.response_text`, produces
`BrandMention` rows. Knows nothing about scoring.

**`citation_scorer.py`** — Reads `BrandMention` rows, produces
`BrandScore` rows including cross-platform deltas and archetype
classification. Knows nothing about extraction.

The separation means extraction can be re-run independently if the
dictionary is updated, without invalidating existing scores. And scoring
logic can be recalibrated without touching extraction.

---

## Part 1: Brand Extractor

### File: `app/core/brand_extractor.py`

### Responsibility

Convert raw LLM response text into structured `BrandMention` rows.
Two sequential passes per `RunResult`:

```
RunResult.response_text
    │
    ├── Pass 1: Rule-based extraction
    │       └── String match against brand_dictionary
    │       └── Fast, cheap, handles ~80% of cases
    │
    ├── Pass 2: LLM-assisted extraction (conditional)
    │       └── Only runs if Pass 1 found < MIN_BRANDS_RULE_PASS brands
    │       └── Catches new/unknown brands
    │       └── Promotes new brands to brands table
    │
    └── BrandMention rows written to DB
```

### Constants (defined in `app/core/config.py`)

```python
MIN_BRANDS_RULE_PASS = 3
# Minimum brands rule pass must find before LLM pass is skipped.
# If rule pass finds >= 3 brands, LLM pass is skipped for that result.
# Rationale: most responses mention 3-7 brands. If rule pass finds 3+,
# it has likely captured the main brands and LLM pass adds marginal value.

LLM_EXTRACTION_MODEL = "claude-sonnet-4-20250514"
# Uses Claude via Anthropic API for LLM extraction pass.
# Separate from query runner models (OpenAI/Gemini/Perplexity).

LLM_EXTRACTION_CONFIDENCE_DEFAULT = 0.85
# Confidence assigned to LLM-extracted mentions not in dictionary.

RULE_EXTRACTION_CONFIDENCE = 1.0
# Confidence for exact dictionary matches.

MAX_BRANDS_PER_RESPONSE = 20
# Hard cap. If extraction finds > 20 brands, truncate to first 20
# by position. Prevents runaway extraction on unusually long responses.
```

---

### Pass 1: Rule-Based Extraction

#### Function signature

```python
def run_rule_pass(
    response_text: str,
    vertical_id: str,
    db: Session
) -> list[dict]:
    """
    Match brand dictionary terms against response text.

    Args:
        response_text: Full LLM response string
        vertical_id: Used to load the relevant dictionary subset
        db: Database session

    Returns:
        List of match dicts:
        [
            {
                "brand_id": str,
                "canonical_name": str,
                "mention_position": int,   # 1-based, order of first appearance
                "mention_text": str,       # matched term
                "extraction_method": "rule",
                "confidence": 1.0
            },
            ...
        ]
    """
```

#### Algorithm

```
1. Load brand_dictionary entries for vertical_id
   (also load entries with no vertical_id — cross-vertical brands)

2. Build match_terms: list of (term, brand_id, canonical_name)
   sorted by len(term) descending
   Reason: match longest alias first to avoid partial matches.
   "Google Analytics" must match before "Google".

3. Normalise response_text:
   normalised = response_text.lower()

4. For each (term, brand_id, canonical_name) in match_terms:
   a. If brand_id already in matched_brand_ids → skip (FAIL-006 guard)
   b. Find first occurrence of term.lower() in normalised
   c. If found:
      - Record character position
      - Add to matches list
      - Add brand_id to matched_brand_ids set

5. Sort matches by character position (ascending)

6. Assign mention_position 1..N based on sort order

7. Cap at MAX_BRANDS_PER_RESPONSE

8. Return matches
```

#### Boundary conditions

- **Partial word matches:** Use word-boundary check.
  "SAP" must not match inside "SAPSAP" or "Capsaicin".
  Implementation: wrap term in `\b` regex or check surrounding chars.

- **Brand names with punctuation:** Strip trailing punctuation from
  matched span before recording mention_text.
  "HubSpot," → mention_text = "HubSpot"

- **Case sensitivity:** Matching is case-insensitive. mention_text
  records the original casing from response (not the dictionary term).

- **Overlapping matches:** If two dictionary terms overlap in the text,
  the longer match wins (ensured by sorting terms by length descending).

---

### Pass 2: LLM-Assisted Extraction

Only runs when `len(rule_pass_results) < MIN_BRANDS_RULE_PASS`.

#### Function signature

```python
def run_llm_pass(
    response_text: str,
    vertical_id: str,
    rule_pass_results: list[dict],
    db: Session
) -> list[dict]:
    """
    Use Claude to extract brand names missed by rule pass.

    Args:
        response_text: Full LLM response string
        vertical_id: For context in prompt
        rule_pass_results: Already-found brands (to exclude from prompt)
        db: Database session

    Returns:
        List of NEW match dicts not already in rule_pass_results.
        Same structure as run_rule_pass return value, with:
        - extraction_method: "llm"
        - confidence: 0.85 (default) or model-returned confidence
    """
```

#### LLM Extraction Prompt

```python
EXTRACTION_PROMPT_TEMPLATE = """
You are extracting brand and product names from a text passage.

TEXT TO ANALYSE:
{response_text}

ALREADY IDENTIFIED (do not repeat these):
{already_found}

VERTICAL CONTEXT: {vertical_display_name}

INSTRUCTIONS:
1. List every company name, software product, or SaaS tool mentioned
   in the text, in the order they first appear.
2. Return the most specific product name when a company is referenced
   in the context of a specific product.
   Example: "Google Analytics" not "Google" if the text discusses
   Google's analytics product.
3. Do not include generic category terms (e.g. "CRM software",
   "email tool") — only named brands.
4. Do not include brands already in the ALREADY IDENTIFIED list.
5. Return ONLY a JSON array. No preamble, no explanation, no markdown.

RESPONSE FORMAT:
[
  {{"brand": "ExactBrandName", "position": 1}},
  {{"brand": "AnotherBrand", "position": 2}}
]

If no additional brands are found, return: []
"""
```

#### Post-processing LLM output

```python
def process_llm_extraction_output(
    raw_output: str,
    rule_pass_results: list[dict],
    db: Session
) -> list[dict]:
    """
    1. Parse JSON from raw_output (strip markdown fences if present)
    2. Normalise each brand name:
       normalised = re.sub(r"[^\w\s\-\.]", "", raw).strip()
    3. For each normalised brand:
       a. Case-insensitive lookup against brands.canonical_name
       b. Case-insensitive lookup against all known aliases
       c. If match found: use existing brand_id
       d. If no match: create new Brand record
          - canonical_name = normalised (title-cased)
          - source = "llm_extracted"
          - is_verified = False  ← requires human review before public index
          - vertical_id = current vertical
    4. Assign mention_position continuing from last rule_pass position
    5. Return new matches only (not already in rule_pass_results)
    """
```

#### New brand promotion

When LLM pass discovers a brand not in the dictionary:

```
1. Create Brand record (is_verified = False)
2. Create BrandDictionaryEntry for the term + vertical
3. Log in ExtractionRun.new_brands_discovered count
4. Flag for human review in admin UI
   (Streamlit: "Unverified brands" queue)
5. Brand appears in raw data immediately but is EXCLUDED
   from public citation_index until is_verified = True
```

This ensures data quality on the public index without blocking
the extraction pipeline.

---

### Main extraction function

```python
def extract_brands_from_result(
    result: RunResult,
    db: Session
) -> list[BrandMention]:
    """
    Orchestrates Pass 1 and Pass 2 for a single RunResult.
    Writes BrandMention rows to DB.
    Updates result.extraction_status throughout.

    Processing steps:
    1. Set result.extraction_status = "rule_pass_running"
    2. Run Pass 1
    3. Set result.extraction_status = "rule_pass_done"
    4. If len(pass1) < MIN_BRANDS_RULE_PASS:
       - Set result.extraction_status = "llm_pass_running"
       - Run Pass 2
       - Set result.extraction_status = "llm_pass_done"
    5. Merge results, deduplicate by brand_id
    6. Create BrandMention rows
    7. Set result.extraction_status = "complete"
    8. Return BrandMention list
    """
```

### Batch extraction function

```python
def extract_brands_from_run(
    run: QueryRun,
    db: Session
) -> ExtractionRun:
    """
    Runs extraction across all RunResults for a QueryRun.
    Creates ExtractionRun audit record.
    Sets run.extraction_complete = True on completion.

    Error handling:
    - Individual result failures are logged to ExtractionRun.error_log
    - Failed results get extraction_status = "failed"
    - Batch continues after individual failures (no abort)
    - ExtractionRun.status = "partial" if any errors, "complete" if none
    """
```

---

## Part 2: Citation Scorer

### File: `app/core/citation_scorer.py`

### Responsibility

Read `BrandMention` rows for a completed `QueryRun`, compute
`BrandScore` rows per brand × platform × vertical, compute
cross-platform deltas, classify archetypes, and write
`ArchetypeSnapshot` rows.

Scoring runs after extraction is complete (`run.extraction_complete = True`).

---

### Step 1: Per-platform scoring

#### Function signature

```python
def compute_brand_scores(
    run: QueryRun,
    db: Session
) -> list[BrandScore]:
    """
    Compute citation scores per brand × platform × vertical for a run.

    Processing:
    1. Group BrandMentions by (brand_id, platform_id, vertical_id)
    2. For each group, compute:
       - total_mentions
       - queries_cited_in (distinct panel_query_ids)
       - first_position_count
       - url_cited_count
       - citation_score (position-weighted)
    3. Normalise scores within platform × vertical × run
    4. Assign ranks within platform × vertical × run
    5. Compute baseline deltas if baseline run exists
    6. Write BrandScore rows
    7. Set run.scoring_complete = True
    """
```

#### Position-weighted scoring

```python
POSITION_WEIGHTS = {1: 5, 2: 3, 3: 2}
POSITION_WEIGHT_DEFAULT = 1
URL_CITED_BONUS = 2

def compute_citation_score(mentions: list[BrandMention]) -> float:
    score = 0.0
    for m in mentions:
        weight = POSITION_WEIGHTS.get(m.mention_position, POSITION_WEIGHT_DEFAULT)
        score += weight
        if m.url_cited:
            score += URL_CITED_BONUS
    return score
```

#### Normalisation

Two-stage, applied within platform × vertical × run:

```python
def normalise_scores(
    scores: dict[str, float],  # brand_id → raw_score
    query_count: int           # queries in this vertical
) -> dict[str, float]:         # brand_id → normalised_score (0-100)
    """
    Stage 1: normalise by query count
        score_per_query = raw_score / query_count

    Stage 2: normalise within group
        max_score = max(score_per_query.values())
        if max_score == 0: return all zeros
        normalised = (score_per_query / max_score) * 100
    """
```

Rationale: raw scores are not comparable across verticals with
different query counts or brand density. Normalised scores are.
Raw scores are stored in `brand_scores.citation_score`.
Normalised scores are stored in `brand_scores.citation_score_normalised`.
Public index displays normalised only.

---

### Step 2: Cross-platform deltas

Runs after all platform scores for a run are written.

```python
def compute_cross_platform_deltas(
    run: QueryRun,
    db: Session
) -> None:
    """
    For each (brand_id, vertical_id) pair in this run:

    1. Fetch BrandScore rows for chatgpt, perplexity, gemini
       (may be missing if brand not mentioned on a platform — treat as 0)

    2. Compute:
       perplexity_vs_chatgpt_delta = perplexity_normalised - chatgpt_normalised
       perplexity_vs_gemini_delta  = perplexity_normalised - gemini_normalised
       chatgpt_vs_gemini_delta     = chatgpt_normalised - gemini_normalised
       platform_variance           = stdev([chatgpt, perplexity, gemini])

    3. Denormalise scores onto each platform's BrandScore row:
       brand_score.chatgpt_score_this_run    = chatgpt_normalised
       brand_score.perplexity_score_this_run = perplexity_normalised
       brand_score.gemini_score_this_run     = gemini_normalised
       brand_score.perplexity_vs_chatgpt_delta = ...
       brand_score.platform_variance = ...

    4. Update brand.platform_citation_summary JSON

    Note: brands not mentioned on a platform get a score of 0 for
    that platform — they are NOT excluded from delta computation.
    A brand with chatgpt_normalised=60 and perplexity_normalised=0
    has a delta of -60 and is a strong ghost/training_dependent signal.
    """
```

#### Handling missing platform scores

A brand may appear in ChatGPT responses but not Perplexity responses.
This is a valid and important data point — absence is not missing data,
it is a zero score.

```python
def get_score_or_zero(
    brand_id: str,
    platform_slug: str,
    vertical_id: str,
    run_id: str,
    db: Session
) -> float:
    score = db.query(BrandScore).filter_by(
        brand_id=brand_id,
        platform_slug=platform_slug,  # via join
        vertical_id=vertical_id,
        run_id=run_id
    ).first()
    return score.citation_score_normalised if score else 0.0
```

---

### Step 3: Archetype classification

Runs after cross-platform deltas are computed.
`run.gap_analysis_valid` must be True before this step runs.

```python
def classify_archetype(
    chatgpt_score: float,
    perplexity_score: float,
    gemini_score: float,
    perplexity_vs_chatgpt_delta: float,
    platform_variance: float,
    thresholds: dict = ARCHETYPE_THRESHOLDS
) -> tuple[str, float, dict]:
    """
    Classify a brand into one of five archetypes.

    Returns:
        (archetype_slug, confidence, signals_dict)

    Classification logic (priority order):

    1. consensus_dominant
       chatgpt >= 50 AND perplexity >= 50 AND gemini >= 50
       AND platform_variance <= 15
       → confidence = min(chatgpt, perplexity, gemini) / 100
         (how strongly all platforms agree)

    2. ghost
       chatgpt >= 35 AND perplexity <= 15
       → confidence = (chatgpt - perplexity) / 100

    3. training_dependent
       chatgpt >= 50 AND perplexity_vs_chatgpt_delta <= -20
       → confidence = abs(delta) / 100

    4. retrieval_driven
       perplexity >= 40 AND perplexity_vs_chatgpt_delta >= 15
       → confidence = delta / 100

    5. consensus_geo
       all platforms 25-60 AND platform_variance <= 15
       → confidence = 0.5 (always flagged for manual review)
       → is_verified = False until backlink check done

    6. unclassified
       no threshold met
       → confidence = 0.0
    """
```

#### Confidence scoring rationale

Confidence is not the model's certainty — it is how far the brand's
scores exceed the classification thresholds. A brand with
chatgpt=95, perplexity=5 is a higher-confidence training_dependent
than a brand with chatgpt=55, perplexity=32.

This allows the public index to surface "strongly training-dependent"
vs "marginally training-dependent" brands — a meaningful distinction
for brand managers reading the index.

#### `consensus_geo` flag

`consensus_geo` is always returned with `archetype_confidence = 0.5`
regardless of score levels, because it cannot be confirmed without
external backlink data. The admin UI shows a "Needs backlink review"
queue for all `consensus_geo` candidates.

---

### Step 4: Write ArchetypeSnapshot

```python
def write_archetype_snapshots(
    run: QueryRun,
    db: Session
) -> None:
    """
    For each (brand_id, vertical_id) pair with complete cross-platform
    delta data:

    1. Fetch previous ArchetypeSnapshot for this brand × vertical
       (most recent run before current)

    2. Compute archetype using classify_archetype()

    3. Write ArchetypeSnapshot row with:
       - previous_archetype from step 1 (or None)
       - archetype_changed = (new != previous)
       - Denormalised score snapshot
       - archetype_threshold_version from config

    4. Update brand.latest_archetype
    5. Set run.archetype_complete = True
    """
```

---

### Step 5: Index builder trigger

After archetype snapshots are written, `index_builder.py` is called
(separate module — not in citation_scorer.py):

```python
def build_citation_index(run: QueryRun, db: Session) -> None:
    """
    Materialise citation_index rows from brand_scores +
    archetype_snapshots for the completed run.

    For each (index_type, platform_slug, vertical_slug) combination:
    1. Rank brands by citation_score_normalised descending
    2. Compute trend_direction vs baseline
    3. Attach archetype classification from ArchetypeSnapshot
    4. Write citation_index rows
    5. Prune old snapshots (retain last 13 runs)
    6. Set run.index_built = True
    7. Trigger Next.js rebuild signal
    """
```

---

## Full Pipeline Sequence

```
QueryRun status: "complete"
    │
    ▼
extract_brands_from_run()
    └── For each RunResult:
        ├── run_rule_pass()
        ├── run_llm_pass() [if needed]
        └── Write BrandMention rows
    └── Write ExtractionRun audit record
    └── run.extraction_complete = True
    │
    ▼
compute_brand_scores()
    └── Group mentions → raw scores
    └── Normalise within platform × vertical × run
    └── Assign ranks
    └── Compute baseline deltas
    └── Write BrandScore rows
    └── run.scoring_complete = True
    │
    ▼
compute_cross_platform_deltas()
    └── For each brand × vertical:
        ├── Fetch scores for all 3 platforms (0 if missing)
        ├── Compute deltas + variance
        └── Update BrandScore rows
    └── Update brand.platform_citation_summary
    │
    ▼ (only if run.gap_analysis_valid = True)
write_archetype_snapshots()
    └── classify_archetype() per brand × vertical
    └── Write ArchetypeSnapshot rows
    └── Update brand.latest_archetype
    └── run.archetype_complete = True
    │
    ▼
build_citation_index()
    └── Materialise citation_index rows
    └── Prune old snapshots
    └── run.index_built = True
    └── Trigger Next.js rebuild
```

---

## Test Coverage Plan

### `tests/test_brand_extractor.py`

| Test | What it covers |
|------|---------------|
| `test_rule_pass_basic` | Finds known brands in simple response |
| `test_no_double_count_on_aliases` | FAIL-006 guard — alias deduplication |
| `test_longest_match_wins` | "Google Analytics" beats "Google" |
| `test_word_boundary` | "SAP" not matched inside "SAPSAP" |
| `test_position_ordering` | Brands ordered by first appearance |
| `test_position_cap` | MAX_BRANDS_PER_RESPONSE enforced |
| `test_llm_pass_triggered` | LLM pass runs when rule pass < MIN_BRANDS_RULE_PASS |
| `test_llm_pass_skipped` | LLM pass skipped when rule pass >= MIN_BRANDS_RULE_PASS |
| `test_llm_extraction_normalisation` | FAIL-007 guard — punctuation stripping |
| `test_product_vs_parent_disambiguation` | FAIL-008 guard — "Google Analytics" not "Google" |
| `test_new_brand_promotion` | New brand creates unverified Brand record |
| `test_extraction_status_updates` | result.extraction_status transitions correctly |
| `test_batch_extraction_continues_on_error` | Single failure doesn't abort batch |

### `tests/test_citation_scorer.py`

| Test | What it covers |
|------|---------------|
| `test_position_weights` | pos1=5, pos2=3, pos3=2, pos4+=1 |
| `test_url_cited_bonus` | +2 for url_cited |
| `test_two_stage_normalisation` | FAIL-009 guard — cross-vertical comparability |
| `test_cross_platform_delta_positive` | retrieval_driven signal computed correctly |
| `test_cross_platform_delta_negative` | training_dependent signal computed correctly |
| `test_missing_platform_score_is_zero` | Absent platform treated as 0, not null |
| `test_platform_variance` | stdev computation across 3 platforms |
| `test_archetype_consensus_dominant` | All platforms high + low variance |
| `test_archetype_training_dependent` | High ChatGPT, low Perplexity |
| `test_archetype_retrieval_driven` | High Perplexity, lower ChatGPT |
| `test_archetype_ghost` | ChatGPT moderate, Perplexity near zero |
| `test_archetype_consensus_geo` | Consistent moderate scores |
| `test_archetype_unclassified` | No threshold met |
| `test_archetype_priority_order` | consensus_dominant beats ghost when both met |
| `test_archetype_changed_flag` | archetype_changed = True when archetype shifts |
| `test_gap_analysis_invalid_skips_archetype` | Archetype not written if gap_analysis_valid = False |
| `test_consensus_geo_confidence_fixed` | consensus_geo always returns confidence = 0.5 |

---

## Failure Registry Entries (pre-populated)

See `knowledge/failure_registry.yml` for:
- FAIL-006: alias double-counting in rule pass
- FAIL-007: LLM extraction normalisation
- FAIL-008: product vs parent disambiguation

New entries to add after first run:
- Any cases where MIN_BRANDS_RULE_PASS threshold proves too high or low
- Any archetype misclassification patterns observed in QA review
- Any LLM extraction prompt failures on specific response formats
