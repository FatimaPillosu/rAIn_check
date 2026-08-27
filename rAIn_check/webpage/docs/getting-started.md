# Getting Started

rAIn_check runs **fully on your machine** — CPU-only, no admin rights, no cloud. This page
gets you from a fresh clone to the guided rail.

> These instructions target **Windows** (the partner-machine reference), matching `run.bat`.
> Requires **Python 3.11**.

---

## Quick start

```bat
cd rAIn_check
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install llama-cpp-python==0.3.34 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
.venv\Scripts\python.exe scripts\make_golden.py
.venv\Scripts\python.exe scripts\make_demo_pack.py
run.bat
```

`run.bat` opens **http://127.0.0.1:8501** — the guided rail:
**Data → Checks → Scores → Maps & case studies → Report.**

```mermaid
flowchart LR
    V[🐍 Create venv] --> I[📦 Install deps] --> LL[🧠 Install llama-cpp CPU wheel] --> G[🧪 make_golden] --> D[🎒 make_demo_pack] --> R[🚀 run.bat]
    style R fill:#2ea043,color:#fff,stroke:none
    style V fill:#1f6feb,color:#fff,stroke:none
```

---

## Why the separate `llama-cpp-python` line?

There's **no C++ compiler** on the reference machine (no Visual Studio Build Tools, no admin
rights assumed). A plain `pip install` tries to **build from source and fails**. The
`--extra-index-url` above serves a **prebuilt Windows CPU wheel** instead. This is the one
install step that most commonly trips people up — use the line as written.

---

## Try the full flow

On the **Data** step, pick the `samples/` forecast + observation files. The demo pack's
station file is **deliberately messy** — that's on purpose, so you experience a real
**recipe approval** ([propose → approve → execute → explain](ai-assistant.md)) rather than a
sanitised happy path.

→ Walk through every step with screenshots: **[The Five-Step Rail](five-step-rail.md)**

---

## Running the tests

```bat
cd rAIn_check
.venv\Scripts\python.exe -m pytest tests\
```

**84 tests, all passing** as of this build. Coverage includes:

- CRPS cross-validated against the independent `properscoring` package to 1e-6 tolerance
- Hand-computed degenerate cases (single member, all-zero rainfall, exact ties)
- The golden-dataset regression suite and QC checks
- Ingestion recipes (including a date-format-ambiguity test)
- The demo pack's full pipeline, end to end, and figure rendering
- The assistant: tool registry, triage rules, knowledge cards, grammar — plus two tests that
  load the **real GGUF models** and verify grammar-constrained tool-calling actually works

---

## The two models

Both are downloaded, licence-verified, and working, and you toggle them in the dock. Full
comparison: **[The Local Models](local-models.md)**. Prefer to run with no model at all? Select **"None"** —
the deterministic fallback keeps the assistant working.

---

## Before you rely on it for real analysis

This is a **prototype (v0.1.0)** — a first end-to-end build, honest about what is and isn't
finished (GRIB not yet run against a real file, RAM target not yet met on true 4 GB hardware,
no portable installer yet). **Read [Roadmap and Limitations](roadmap-and-limitations.md) first.**
