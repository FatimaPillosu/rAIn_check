"""The Week-5 / Step-S5 model gate (plan §9): peak RAM <= 1.8GB at 2k context,
>= 4 tokens/s, >= 95% valid-JSON rate on 30 canned tool-call prompts. Run against both
configured models and record the report — this decides each machine's default
capability level (plan §9's L3/L2/L1 ladder).

Note: peak RSS is dominated by model size + KV cache, which is largely
hardware-independent for a given model/context, so this is meaningful even though
tonight's run is on a development machine, not the 4GB reference machine (plan §2).
Tokens/second, however, IS hardware-dependent (CPU speed/cores) and will likely be
higher here than on the reference machine — treat the tokens/s figure as an upper bound,
not a guarantee, until re-measured on reference-class hardware.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assistant.adapter import ModelLoadError, get_adapter
from assistant.config import load_assistant_config

RAM_BUDGET_MB = 1800
MIN_TOKENS_PER_SEC = 4.0
MIN_VALID_JSON_RATE = 0.95

TOOLS_HELP = (
    "Available tools: list_data (no args), inspect_file(path), propose_recipe(path), "
    "run_qc (no args), compute_scores(scores, thresholds_mm, leads), "
    "make_plot(kind, params), get_card(topic), explain_last_error (no args). "
    "Respond only with a single JSON tool call, nothing else."
)

# 30 canned prompts spanning every tool in the registry, several phrasings each, plus a
# few deliberately ambiguous/adversarial ones (plan requires this specific count).
CANNED_PROMPTS = [
    "What data files do we have available?",
    "Show me what forecast and observation files exist.",
    "List everything in the data folders.",
    "Can you peek at data/samples/pseudo_stations.csv for me?",
    "Take a look inside the forecast file and tell me its dimensions.",
    "Preview the observations file before we load it.",
    "This station file doesn't match the expected format — propose a mapping for data/samples/pseudo_stations.csv.",
    "Work out how to read this messy CSV: data/samples/pseudo_stations.csv.",
    "Propose an ingestion recipe for the pseudo stations file.",
    "Please run the quality control checks on the current data.",
    "Check the observations for problems.",
    "Are there any QC issues I should know about?",
    "Compute CRPS and BSS for lead day 1 at the 5 and 20mm thresholds.",
    "Give me the verification scores for lead 1, thresholds 1 5 20 50.",
    "I want CRPS, rank histogram and spread-error for leads 1 and 2.",
    "Score the forecast using every available metric at lead 3.",
    "Make a rank histogram plot.",
    "Can you draw the reliability diagram for the 20mm threshold?",
    "Plot the exceedance probability map.",
    "Show me a postage-stamp plot of the ensemble members.",
    "I want a map of the ensemble mean.",
    "What does CRPS mean?",
    "Explain the Brier skill score to me.",
    "Tell me about the rank histogram — how do I read it?",
    "What's a reliability diagram?",
    "Explain the ROC curve.",
    "What went wrong last time — can you explain the last error?",
    "Something failed earlier, what was it?",
    "Diagnose the last error for me.",
    "Give me the spread-error ratio card.",
]

assert len(CANNED_PROMPTS) == 30, f"expected exactly 30 canned prompts, got {len(CANNED_PROMPTS)}"


def _count_tokens(adapter, text: str) -> int:
    try:
        return len(adapter._llm.tokenize(text.encode("utf-8")))
    except Exception:
        return max(1, len(text) // 4)  # rough fallback estimate


def _mem_mb(process: psutil.Process) -> tuple[float, float]:
    """(working_set_mb, private_mb). On Windows, llama.cpp memory-maps the GGUF file by
    default, so 'rss'/working-set includes OS-reclaimable mapped file pages touched
    during inference and can look alarmingly high — 'private' (non-shared, committed
    memory) is the metric that actually matters for "will this exhaust a 4GB machine".
    Falls back to rss for both on platforms without a 'private' field.
    """
    mem = process.memory_info()
    private = getattr(mem, "private", mem.rss)
    return mem.rss / 1e6, private / 1e6


def benchmark_one(model_key: str, config) -> dict:
    process = psutil.Process()
    baseline_ws_mb, baseline_priv_mb = _mem_mb(process)

    adapter = get_adapter(model_key, config)
    report: dict = {"model_key": model_key, "label": config.models[model_key].label}

    try:
        t0 = time.time()
        adapter.load()
        report["load_seconds"] = round(time.time() - t0, 2)
    except ModelLoadError as exc:
        report["error"] = str(exc)
        return report

    peak_ws_mb, peak_priv_mb = baseline_ws_mb, baseline_priv_mb
    valid_json = 0
    total_tokens = 0
    total_seconds = 0.0
    failures = []

    for i, prompt in enumerate(CANNED_PROMPTS):
        messages = [
            {"role": "system", "content": TOOLS_HELP},
            {"role": "user", "content": prompt},
        ]
        t0 = time.time()
        try:
            result = adapter.generate(messages, use_grammar=True)
            valid_json += 1
            elapsed = time.time() - t0
            total_seconds += elapsed
            total_tokens += _count_tokens(adapter, json.dumps(result.__dict__))
        except Exception as exc:
            failures.append({"prompt": prompt, "error": str(exc)[:300]})

        ws_mb, priv_mb = _mem_mb(process)
        peak_ws_mb = max(peak_ws_mb, ws_mb)
        peak_priv_mb = max(peak_priv_mb, priv_mb)

    adapter.unload()

    report["peak_working_set_mb"] = round(peak_ws_mb, 1)
    report["peak_private_mb"] = round(peak_priv_mb, 1)
    report["ram_budget_mb"] = RAM_BUDGET_MB
    report["ram_within_budget"] = peak_priv_mb <= RAM_BUDGET_MB  # gate on private, not working-set — see _mem_mb docstring
    report["valid_json_rate"] = round(valid_json / len(CANNED_PROMPTS), 3)
    report["valid_json_meets_gate"] = (valid_json / len(CANNED_PROMPTS)) >= MIN_VALID_JSON_RATE
    report["tokens_per_second"] = round(total_tokens / total_seconds, 2) if total_seconds > 0 else 0.0
    report["speed_meets_gate"] = report["tokens_per_second"] >= MIN_TOKENS_PER_SEC
    report["passes_gate"] = report["ram_within_budget"] and report["valid_json_meets_gate"] and report["speed_meets_gate"]
    report["failures"] = failures
    return report


def main():
    config = load_assistant_config()

    # Each model is benchmarked in its own subprocess: llama.cpp's native allocations
    # aren't always reclaimed from process RSS immediately after unload() (Python's
    # allocator doesn't necessarily return freed memory to the OS), so benchmarking two
    # models back-to-back in one process contaminates the second model's peak-RSS
    # reading with the first model's leftover footprint. A fresh process per model gives
    # each an accurate, isolated peak RSS.
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        model_key = sys.argv[2]
        print(json.dumps(benchmark_one(model_key, config)))
        return

    import subprocess
    reports = []
    for key in config.models:
        print(f"Benchmarking {key} (isolated subprocess)...")
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--single", key],
            capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]),
        )
        stdout_lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
        json_line = next((l for l in reversed(stdout_lines) if l.startswith("{")), None)
        if json_line is None:
            reports.append({"model_key": key, "error": f"subprocess produced no report; stderr tail: {proc.stderr[-1000:]}"})
        else:
            reports.append(json.loads(json_line))

    out_path = Path(__file__).resolve().parents[1] / "workspace" / "model_gate_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(reports, indent=2), encoding="utf-8")

    for r in reports:
        if "error" in r:
            print(f"  {r['model_key']}: FAILED TO LOAD — {r['error']}")
            continue
        status = "PASS" if r["passes_gate"] else "FAIL"
        print(f"  {r['model_key']}: {status} — peak private RAM {r['peak_private_mb']}MB "
              f"(working set {r['peak_working_set_mb']}MB; budget {RAM_BUDGET_MB}MB), "
              f"{r['tokens_per_second']} tok/s, {r['valid_json_rate']*100:.1f}% valid JSON, "
              f"{len(r['failures'])} failures")
    print(f"\nFull report: {out_path}")


if __name__ == "__main__":
    main()
