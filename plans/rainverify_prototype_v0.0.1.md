# Rainfall Verification Prototype — 8-Week Implementation Brief



Working title: `rAIn\_check`.

## 

## 1\. Objective

Build a demonstrable prototype of a locally run, AI-assisted ensemble rainfall verification system for meteorologists who know their regional climatology well but have little Python and ensemble forecasts background. The system guides the user through verification; it never runs the analysis end-to-end on its own. After a single download, the prototype of the AI-based system must run fully offline on the reference machine.

## 

## 2\. Reference machine and hard constraints

* Windows 10-11 64-bit, 4 GB RAM, \~100 GB free disk, CPU only, no admin rights, old browser (Chrome 109-era). Server-rendered HTML only; no modern JS frameworks; no build step. \[AUTHOR: in the final plan, as a docx, we should have screenshots of how the system looks like].
* All data and all AI inference stay on the machine. No network calls at runtime.
* Installed footprint ≤ 8 GB total: environment ≈ 2.5 GB, model ≈ 2 GB, sample data ≤ 1 GB.
* RAM budgets, enforced by tests using `psutil`: engine peak ≤ 1.2 GB; web app steady ≤ 300 MB; LLM ≤ 1.8 GB at 2k context. The model and heavy score computation must never run simultaneously — free or suspend the model before large computations.
* Process forecast data lazily (xarray chunking); never load a full ensemble cube into memory.

\[AUTHOR: in the final version of the plan, we should write what these choices are (i.e., describe them for non-technical people) and why we are taking these choices, while maintaining the dignity of the users of this system. This system is covering a gap in code sharing with countries in the global south.]

## 

## 3\. Architecture — three layers

1. **Verification engine** (deterministic; owns every number): pure NumPy/Pandas score functions with xarray/NetCDF I/O and a CLI. The system is intelligent enough to understand whether something is not included yet in its code repository (e.g., there is no code to compute the area under the ROC curve), and create it with scientific rigour, checking with the scientist at different stages of the process, so the formulas and the concepts are all correct. 
2. **Guided GUI**: a fixed five-step rail — Data → Checks → Scores → Maps \& case studies → Report — plus a chat dock. ~~Fully usable with the assistant switched off.~~ \[AUTHOR: I never want the AI assistant switched off, it should always be there to advice and assist the scientist at all times.]
3. **Local assistant**: a small GGUF\* model behind a model-agnostic adapter; a fixed tool registry; JSON-only tool calls enforced by a llama.cpp GBNF grammar\*1; answers about verification retrieved from local knowledge cards. Interaction loop: propose → user approves → execute via engine → explain. The model never generates numeric results or formulas from memory; it calls tools and quotes cards.

\[AUTHOR: \*GGUF (GPT-Generated Unified Format) is a single-file binary format designed to store and run large language models (LLMs) efficiently on everyday consumer hardware, like personal laptops and desktop computers.]

1. \[AUTHOR: \*1 "llama.cpp GBNF grammar", it needs to be explained]

## 

## 4\. Tech stack (pin exact versions in `requirements.txt`)

* Python 3.11. numpy, pandas, xarray, h5netcdf, matplotlib, seaborn, cartopy (binary wheels).
* Maps: try `earthkit-plots` first; timebox half a day in Week 1. If installation on Windows is troublesome, fall back to cartopy + matplotlib. {AI: Do not use earthkit-data in the prototype — it pulls in eccodes, historically the fragile component on Windows. ~~The prototype is NetCDF end-to-end; GRIB decoding happens on the forecast-provider side~~. We need to have the possibility to work with both NetCDF and grib. The system should be smart enough to understand what we are using, and so call the right libraries to work with.}
* Web: fastapi, uvicorn, jinja2, htmx (vendor the single htmx.min.js file).
* LLM: llama-cpp-python, prebuilt CPU wheel.
* Tests: pytest. Dev-only (never shipped): `xskillscore` or the BoM `scores` package for cross-validation.
* Packaging: conda-pack portable zip + `run.bat` (per-user, no registry writes, launches server and opens the default browser at `http://127.0.0.1:8501`).

## 

## 5\. Repository layout

```
rainverify/
  engine/        # scores, qc, matching, bootstrap, manifest
  app/           # fastapi routes, templates/, static/
  assistant/     # adapter.py, tools.py, grammar.gbnf, triage\_rules.py
  cards/         # one .md knowledge card per score/topic
  data/          # samples/ (demo pack), golden/ (self-test)
  scripts/       # make\_golden.py, make\_demo\_pack.py, benchmark\_model.py
  tests/
  run.bat  README.md  requirements.txt
```

\[AUTHOR: is this the simplest, yet the most effective way of organising the repository? How do you organise the tests and data when the data itself can be of any type? ]

## 

## 6\. Data contracts

* **Forecasts**: NetCDF \[AUTHOR: and grib], dims `(forecast\_reference\_time, lead\_day, member, lat, lon)`; variable `tp` = 24-h precipitation accumulation in mm, float32; global attrs include `accumulation\_hours: 24` and `accumulation\_end\_utc`.
* **Observations**: CSV with header `station\_id,name,lat,lon,elevation\_m,date,accum\_hours,precip\_mm,qc\_flag`. \[AUTHOR: it is true that the most common format for the observations is going to be this one, however, there are going to be other ones and we should somehow let the intelligent ai-based system that that might happen so it needs to adapt, perhaps by reading the files that the scientist tells it are the observations or reading the documentation provided with the files.]

  * Example: `TZ0042,Moshi,-3.35,37.33,890,2026-03-14,24,31.2,0`
* **Golden dataset** (`data/golden/`): a tiny analytic case with hand-computable expected values (e.g. 5 stations × 20 days × 10 members drawn from known distributions), plus `expected.json`. `scripts/make\_golden.py` regenerates it deterministically (fixed seed). First-run self-test recomputes all scores and compares to `expected.json`. \[AUTHOR: again here "expected" does mean much because the observations, as well as the forecasts, can be organised in a variety of ways. They might not even be very well organised, so we need to let the intelligent AI-based system know that. This is one the best characteristics of this AI-based system, beause organising the input data (fc and obs) is more than 80% of the time of a scientist that wants to do any verification analysis, so this AI-based system is basically taking care of it automatically.]
* **Demo pack** (`data/samples/`): ECMWF open-data ENS 24-h precipitation, cropped to an East Africa domain of roughly 10° × 10° at 0.25°, \~60–90 daily runs, leads 1–5 days; plus \~30 **pseudo-stations** generated by sampling a held-out perturbed member with added noise and occasional gaps/outliers. {AI: Pseudo-observations keep the demo honest with respect to the data-sovereignty story — no real partner observations exist anywhere in the prototype — and they give the QC step something to catch. VERIFY the current ECMWF open-data licence and attribution text before bundling.} \[AUTHOR: this is fine, however, we should try to minimise the pre-processing of any raw data. That should be done by the AI system following a natural language request from the scientist. In the case of ECMWF, should the users have access to the MARS archive, they should input their API and download the data that they want, again, following a natural language request. Or better, could be created an MCP to connect the Mars Archive or other forecasts sources to the AI verification system?]
* Rough sizes: demo pack ≤ 300 MB; well within the 100 GB disk. \[AUTHOR: again, is this demo pack of any use at all given the massive difference in data that we are catering for? ]

## 

## 7\. Verification engine ~~(Week 2)~~

Implement as small, readable, individually documented functions — the assistant will teach from this code.

* Scores v1: ensemble CRPS with the Hersbach (2000) decomposition; rank histogram with a chi-square flatness test; Brier score and BSS at thresholds 1, 5, 20, 50 mm/24 h; reliability diagram data (10 bins, with sharpness counts); ROC curve and AUC; spread–error ratio; ensemble-mean bias and MAE.
* Reference forecast for skill scores: sample climatology built from the observation series itself.
* Uncertainty: moving-block bootstrap (block length 5 days, 1,000 resamples) for CIs on CRPS and BSS; emit a warning whenever any stratum has fewer than 30 forecast–observation pairs.
* Matching: nearest grid point (record the chosen point per station). Hard-fail with a clear message if forecast and observation accumulation windows disagree.
* Validation: agreement with the dev reference package within 1e-6 relative tolerance on golden and demo data; unit tests per score including degenerate cases (all-zero rainfall, single member, ties).
* Every run writes `manifest.json`: input file SHA-256 hashes, code version, parameters, timestamps. \[AUTHOR: I don't think I understand what this json file is for. Can you explain it better, and why is this needed?]

## 

## 8\. Guided GUI ~~(Weeks 3–4)~~

* One route per rail step; large primary buttons; grey out steps until prerequisites are met; every page has a collapsible "What am I looking at?" panel with static explanatory text (works with the assistant off).
* **Data**: pick forecast file and observation CSV; show a summary table (period, stations, members, leads).
* **Checks**: QC results (range 0–500 mm/24 h, spike, duplicate, gap counts) and the accumulation-window check, each with pass/warn/fail badges.
* **Scores**: tick-box selection of scores, thresholds, lead times; results as Seaborn figures with CIs; one-click PNG download per figure.
* **Maps \& case studies**: pick a date; render ensemble mean, probability of exceedance for a chosen threshold, and a postage-stamp grid of members, with station observations overlaid. 
* **Report**: single self-contained HTML file with embedded PNGs, the score tables, and the manifest; the user prints to PDF from the browser.

\[AUTHOR: the AI system should give the possibility to the scientist to request modifications and added capabilities through natural language through the power of the LLM used.]

## 

## 9\. Assistant ~~(Weeks 5–6)~~

* **Adapter**: `generate(messages, grammar=None) -> ToolCall | Text` over llama-cpp-python; model path and context length from `config.toml`.
* **Candidate models**: Ministral 3 3B Instruct (Apache 2.0; preferred if it passes the gate — the project narrative favours a European model) and Gemma 4 E2B (smaller footprint; verify its licence terms). **Week 5, day 1 gate** on the reference machine using `scripts/benchmark\_model.py`: peak RAM ≤ 1.8 GB, ≥ 4 tokens/s, ≥ 95 % valid-JSON rate on 30 canned tool-call prompts. Default to the best model that passes; if neither passes, ship "assistant off" as default and record results in the README. Document the LAN inference-server alternative in the README only — do not build it.
* **Tool registry** (read-only except plots/reports, which write to the workspace): `list\_data`, `inspect\_file(path)`, `run\_qc()`, `compute\_scores(spec)`, `make\_plot(spec)`, `get\_card(topic)`, `quiz(topic)`, `explain\_last\_error()`.

  * Example tool call: `{"tool": "compute\_scores", "args": {"scores": \["crps", "bss"], "thresholds\_mm": \[20], "leads": \[1, 3]}}`
* **Conversation policy**: the assistant proposes exactly one action per turn with a one-sentence reason; the UI renders Approve / Modify / Skip buttons; after execution the engine's summary is shown verbatim, then the assistant explains it in ≤ 120 words and asks one interpretation question back to the user.
* **Error triage, rules first**: a table of ≥ 15 regex-classified failure modes (file not found, encoding, date parse, unit mismatch, memory, malformed NetCDF…), each mapping to a fixed diagnosis and fix suggestion; the LLM only narrates the matched diagnosis. If nothing matches, pass only the last 15 traceback lines to the model, clearly labelled as unverified.
* **Knowledge cards** (`cards/\*.md`): definition in plain language; a worked example using about five numbers; common misreadings; what good and bad look like for rainfall specifically. The assistant answers score questions solely by summarising a card, and the UI displays the card title as the source. If no card matches, the assistant says so and does not improvise.

  * Example card skeleton: `# Rank histogram` / `## What it is` / `## Worked example (5 numbers)` / `## Common misreadings` / `## Reading it for rainfall`
* **Guardrails**: refuse to state formulas from memory; log every tool call and outcome to `runlog.jsonl`; assistant has no file-write access outside the workspace.

## 

## 10\. Week-by-week schedule and acceptance criteria

* **W1**: repo scaffold, pinned environment builds on Windows, data contracts implemented, `make\_golden.py` + `make\_demo\_pack.py` working. *Accept*: golden dataset regenerates deterministically; demo pack loads lazily under the RAM budget.
* **W2**: engine scores + bootstrap + manifest. *Accept*: all tolerance tests pass against the dev reference package.
* **W3**: Seaborn figures and map plots (earthkit-plots or fallback decided). *Accept*: every v1 score has a publication-quality figure from demo data.
* **W4**: GUI end-to-end without AI; **Demo 1** script written (10-minute walkthrough: load → QC → CRPS/BSS with CIs → exceedance map → report). *Accept*: a non-developer completes the flow on the reference machine using only the mouse.
* **W5**: LLM adapter, model gate run and decided, tool registry callable from chat. *Accept*: gate report committed; 30-prompt tool-call suite ≥ 95 % valid JSON.
* **W6**: propose/approve loop, triage rules, 8–10 knowledge cards (CRPS, rank histogram, Brier/BSS, reliability, ROC, spread–error, climatology reference, double penalty). *Accept*: three scripted tutoring dialogues run correctly end-to-end.
* **W7**: case-study page polish, report generator, RAM tuning and model load/unload sequencing. *Accept*: full assisted flow stays within RAM budgets on the reference machine (measure, do not estimate).
* **W8**: conda-pack portable zip, `run.bat`, README with install + LAN note + licences, **Demo 2** script; buffer. *Accept*: Definition of done (§13) passes on a fresh Windows 10 VM.

\[AUTHOR: note that I eliminated from the titles the weeks at which each work should be done. Here also those weeks do not mean much, so they should not be considered. At least, not as weeks, but instead as steps that must be done in a certain order, the one here specified.]

## 

## 11\. Descoping ladder (apply in order if behind schedule)

1. Drop the `quiz` tool. 2. Drop ROC (keep its data in the report tables). 3. Reduce cards to the five core scores. 4. Ship the assistant as explain-only (no tool execution; buttons still work). 5. Ship Demo 1 scope with a pre-recorded assistant walkthrough.

## 

## 12\. Definition of done

On a fresh Windows 10 VM with 4 GB RAM: unzip, double-click `run.bat`, browser opens; a first-time user completes Data → Report on the demo pack with assistant guidance in ≤ 20 minutes without touching a console; the golden self-test passes; peak RAM stays within §2 budgets; the report regenerates identically from its manifest.

## 

## 14\. VERIFY before 

Ministral 3 3B licence text as shipped on Hugging Face; Gemma 4 licence terms; earthkit-plots installability on Windows; ECMWF open-data terms and required attribution; llama-cpp-python CPU wheel runs on the reference CPU; conda-pack output unzips and runs without admin rights.

