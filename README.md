# SIP User Discovery Engine

AI-powered product discovery for Systematic Investment Plan (SIP) users. This repository is the project scaffold for a Product Management assignment: it defines where data lives, how the analysis pipeline is organised, and how results will eventually be reviewed. Data processing and model logic are not implemented yet.

## Purpose

Product teams need a repeatable way to turn raw SIP user evidence into decisions. The engine is meant to:

1. Load raw user data (feedback, behaviour, or research exports).
2. Clean and structure that evidence.
3. Classify signals into product-relevant categories.
4. Discover recurring themes.
5. Score those themes as opportunities.
6. Check outputs against a labelled golden set.
7. Present the results in a Streamlit app.

API keys and other secrets stay in a local `.env` file and are never committed.

## Architecture

```text
data/raw  →  data_loader  →  preprocessing  →  data/processed
                                      ↓
                                 classifier
                                      ↓
                              theme_discovery
                                      ↓
                            opportunity_scoring
                                      ↓
                     evaluation  ←  data/golden_set
                                      ↓
                                   app.py
```

| Module | Role |
| --- | --- |
| `src/data_loader.py` | Read source files from `data/raw`. |
| `src/preprocessing.py` | Clean records and write them to `data/processed`. |
| `src/classifier.py` | Label signals into product-relevant categories. |
| `src/theme_discovery.py` | Group related signals into themes. |
| `src/opportunity_scoring.py` | Rank themes as product opportunities. |
| `src/evaluation.py` | Compare outputs with `data/golden_set`. |
| `app.py` | Streamlit interface over the pipeline. |

`data/raw` holds untouched inputs. `data/processed` holds cleaned tables. `data/golden_set` holds labelled examples used only for evaluation.

## Project layout

```text
SIP-Discovery-Engine/
├── data/
│   ├── raw/
│   ├── processed/
│   └── golden_set/
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── preprocessing.py
│   ├── classifier.py
│   ├── theme_discovery.py
│   ├── opportunity_scoring.py
│   └── evaluation.py
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Setup

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put your OpenAI key in `.env`. Do not commit that file. `.env.example` lists the variable names only.

The research dashboard reads the processed secondary-research files already in this project. It does not collect new reviews or comments.

```bash
streamlit run app.py
```

`app.py` shows the Google Play sample, the YouTube comments, the keyword-lead audit, and the written Groww findings. Counts are calculated from those files. Keyword matches stay labelled as leads. The four hypotheses stay unvalidated. The page does not call Gemini or a collection API, and it does not write the datasets.

The sidebar filters apps, the Play problem category, the YouTube lead category, and a text search, and it chooses which filtered table to download. App-comparison charts follow the app selection. Hypothesis counts always use the full files.

The dashboard uses `streamlit`, `pandas`, and `plotly`, which are already listed in `requirements.txt`.

Check the dashboard calculations without opening the browser:

```bash
python -m unittest src.test_dashboard_data -v
```

## YouTube comment consolidation and keyword audit

These commands only read local CSV files. They do not call the YouTube API or Gemini. Keyword matches are leads for a person to check. They are not confirmed investor behaviour.

From the project folder:

```bash
python -m src.consolidate_youtube_batches
python -m src.audit_youtube_evidence
python -m unittest src.test_youtube_comment_audit -v
```

`src.consolidate_youtube_batches` writes `data/processed/youtube_targeted_comments_master.csv` and `data/processed/youtube_targeted_comments_quality_report.md`.

`src.audit_youtube_evidence` writes `data/processed/youtube_evidence_audit.csv` and `data/processed/youtube_evidence_audit.md`. Run the consolidation command first.

## Google Play unfiltered reviews

This sample is English-language reviews from the India Play listing, newest first, with at most 500 reviews per app. It is not a representative sample of all Indian investors. Keyword matches are research leads. They do not prove that a SIP was discontinued, that a cancellation was completed, or that one app is better than another.

Install dependencies first if `google-play-scraper` is not already installed:

```bash
pip install -r requirements.txt
```

From the project folder, collect reviews and write the reports. The command prints a plan and waits. Type `YES` to start. Any other answer cancels before a Play request is made. If `data/raw/google_play_reviews_unfiltered.csv` already exists, the command stops and does not replace it.

```bash
python -m src.google_play_pipeline
```

Rebuild the cleaned table and reports from that saved file without a network request:

```bash
python -m src.google_play_pipeline --analyze-only
```

Run the tests. They use a stand-in scraper and do not contact Google Play:

```bash
python -m unittest src.test_google_play_pipeline -v
```

Outputs:

| File | What it contains |
| --- | --- |
| `data/raw/google_play_reviews_unfiltered.csv` | Reviews as collected, with app name, package id, and collection time. |
| `data/processed/google_play_reviews_master.csv` | Deduplicated reviews, source id, and keyword columns. |
| `data/processed/google_play_sip_evidence.csv` | Reviews marked for manual reading. |
| `data/processed/google_play_quality_report.md` | Empty text, missing ratings and dates, and duplicate ids. |
| `data/processed/google_play_comparative_analysis.md` | Counts by app, rating, relevance, and problem lead. |
| `data/processed/google_play_problem_categories.csv` | Primary problem-category counts by app. |

The older file `data/raw/sip_relevant_reviews.csv` is not changed. If one of the three apps fails, the command does not write the raw file or the reports.

## Secrets

- Store credentials only in `.env` (copied from `.env.example`).
- `.gitignore` excludes `.env`, Python cache, virtual environments, and temporary files.
- `.env.example` is safe to commit because it contains no secret values.
