# Scoring Methodology

Status: Current
Source: `app/core/citation_scorer.py`, `app/core/config.py`

## Overview

The index measures brand citation rates across three AI platforms and computes
the gap between them. The gap is the primary finding.

## Platform roles

| Platform   | retrieval_type   | What it reveals |
|------------|------------------|-----------------|
| ChatGPT    | model_memory     | Historical brand authority — what AI was trained on |
| Perplexity | live_retrieval   | Current live web presence |
| Gemini     | hybrid           | Mixed signal |

## Citation scoring

Each brand mention in a response is scored by position:

| Position | Points |
|----------|--------|
| 1st      | 5      |
| 2nd      | 3      |
| 3rd      | 2      |
| 4th+     | 1      |
| URL cited| +2     |

Raw scores are normalised within platform × vertical × run to a 0-100 scale
(two-stage: per-query normalisation then max-group normalisation).
Normalised scores only are shown publicly.

## Cross-platform delta

`perplexity_vs_chatgpt_delta = perplexity_normalised − chatgpt_normalised`

- Positive delta → brand is stronger on live web than in model memory
- Negative delta → brand is stronger in model memory than on live web

## Archetype classification

Applied only when all 3 platforms complete (`gap_analysis_valid = True`).

| Archetype           | Signal |
|---------------------|--------|
| 👑 Dominant Brand   | All platforms ≥ threshold, low variance |
| 🧠 AI Memory Brand  | ChatGPT high, Perplexity−ChatGPT delta strongly negative |
| 🔍 Live Search Brand| Perplexity high, positive delta |
| 🫥 Fading Brand     | ChatGPT ok, Perplexity near zero |
| ⭐ GEO Outlier      | Consistent across platforms, above what domain authority predicts |

Exact thresholds: `app/core/config.py::ARCHETYPE_THRESHOLDS`
Threshold version is stored on every ArchetypeSnapshot and QueryRun for historical interpretability.

## Bias-flagged queries

Queries where a platform has a structural interest in the outcome
(e.g. "ChatGPT vs Claude" asked to ChatGPT) are marked `bias_flag=True`.
These queries are excluded from archetype scoring aggregation.
Raw data is still stored.

## Query panel design

25 queries across 3 verticals. Five intent types per vertical:
`recommendation`, `best_for`, `comparison`, `category_open`, `temporal`

Temporal queries ("best tools in 2026") amplify the training vs retrieval split most clearly
and are the strongest signal for training_dependent vs retrieval_driven classification.
