# Local assistant models

Downloaded 2026-08-11 for the rAIn_check local-assistant prototype (offline, CPU-only,
llama-cpp-python). Both files were verified: GGUF magic bytes present, on-disk size
matches the Hugging Face listing exactly, and SHA256 matches the repo's LFS checksum
byte-for-byte (no truncation, no HTML error page).

Both model families and licences below were independently confirmed against the
Hugging Face API (raw JSON, not a summarised fetch), the official model-card READMEs,
and the model owners' own announcement pages — not taken from the unverified project
plan. See "Verification notes" at the end for what changed vs. the plan's assumptions.

---

## 1. Ministral 3 3B Instruct 2512

- **HF repo**: `mistralai/Ministral-3-3B-Instruct-2512-GGUF` (official Mistral AI org, quantized and published by Mistral themselves)
- **File**: `Ministral-3-3B-Instruct-2512-Q4_K_M.gguf`
- **Direct URL**: https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF/resolve/main/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
- **Local path**: `assistant/models/ministral-3-3b-instruct-2512-Q4_K_M.gguf`
- **Size on disk**: 2,147,023,008 bytes = 2.00 GiB / 2.15 GB
- **SHA256**: `9ed150d4367e68df0ac8e1540f6ddc65b42d0ee26378329d1ecbca60f93fc5f8` (matches HF LFS oid exactly)
- **Parameters**: 3.4B language model (3.43B per GGUF metadata). A separate 0.4B vision encoder (`Ministral-3-3B-Instruct-2512-BF16-mmproj.gguf`) exists in the same repo but was **not** downloaded — this assistant is text-only (JSON tool calls), so the mmproj file is unneeded weight/RAM.
- **Quantization**: Q4_K_M. This is the smallest quant Mistral themselves publish for this model (repo only offers Q4_K_M, Q5_K_M, Q8_0, BF16 — no Q3 or smaller).
- **Licence**: **Apache 2.0**, confirmed via the repo's `cardData.license` tag (`apache-2.0`) and the README's own text: *"Apache 2.0 License: Open-source license allowing usage and modification for both commercial and non-commercial purposes."*
  - **Plain-language summary**: Apache 2.0 is a standard OSI-approved permissive licence. It permits commercial use, modification, private use, and free redistribution to anyone — including packaging this prototype for partner institutions — with no requirement to open-source anything built on top of it. The only obligations are to keep the copyright/licence notice attached and note any changes made to the licensed files themselves. There is no warranty and no liability on Mistral's part. Separately, Mistral publishes a general Usage/Acceptable Use Policy (illegal activity, weapons, CSAM, etc.) that applies to how the model is *used*, not to redistribution rights — it does not block sharing the weights with partner institutions.
  - **Redistribution to partner institutions: permitted, no restriction.**

---

## 2. Gemma 4 E2B (instruction-tuned)

- **Base model**: `google/gemma-4-E2B-it` (official Google DeepMind org)
- **GGUF repo**: `unsloth/gemma-4-E2B-it-GGUF` (well-known, trusted community GGUF requantizer; base weights are Google's, Unsloth only converts/quantizes)
- **File**: `gemma-4-E2B-it-IQ4_XS.gguf`
- **Direct URL**: https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-IQ4_XS.gguf
- **Local path**: `assistant/models/gemma-4-E2B-it-IQ4_XS.gguf`
- **Size on disk**: 2,983,944,288 bytes = 2.78 GiB / 2.98 GB
- **SHA256**: `c149620926221669c4941ae6dac259953cc729c48e4a4edb69e9807b782fd1e3` (matches HF LFS oid exactly)
- **Parameters**: 2.3B "effective" parameters; 5.1B total including the per-layer embedding (PLE) table. The larger total-with-embeddings figure is why the GGUF file is bigger than a typical dense 2–3B model at the same quant level.
- **Quantization**: **IQ4_XS**, not Q4_K_M. Gemma 4 E2B's own Q4_K_M file is 3,106,738,272 bytes (3.11 GB) — over the ~3 GB ceiling given for this task. IQ4_XS is the next 4-bit option down (2.98 GB, imatrix-calibrated), the largest 4-bit quant that stays under the ceiling. Smaller options exist (Q3_K_M 2.54 GB, Q3_K_S 2.45 GB, UD-Q2_K_XL 2.40 GB, UD-IQ2_M 2.29 GB) but drop below 4 bits/weight, which risks the tool-calling JSON-validity gate more than the RAM budget is worth trading for.
- **Licence**: **Apache 2.0**, confirmed via three independent sources: the HF repo's `license: apache-2.0` tag and `license_link`, the model README's explicit "License: Apache 2.0" line, and Google's own blog post (blog.google, published 2026-04-02) stating Gemma 4 is released under "an Apache 2.0 license" for "complete developer flexibility and digital sovereignty." The `license_link` on the model card resolves to `ai.google.dev/gemma/docs/gemma_4_license`, which itself points to the actual Apache 2.0 text at `ai.google.dev/gemma/apache_2`.
  - **This is a genuine licensing change** — Gemma 1/2/3/3n all shipped under Google's custom, non-OSI "Gemma Terms of Use" (more restrictive than Apache 2.0, with its own redistribution conditions). Gemma 4 (announced April 2026) is the first Gemma generation released under a true Apache 2.0 licence.
  - **Plain-language summary**: same permissions as Apache 2.0 above — commercial use, modification, and free redistribution (including to partner institutions) are all permitted, with only an attribution/notice-of-changes obligation and no warranty. Google separately publishes a non-binding Prohibited Use Policy (`ai.google.dev/gemma/prohibited_use_policy`) covering illegal/harmful/deceptive uses — this is a use-policy overlay, not a redistribution restriction.
  - **Redistribution to partner institutions: permitted, no restriction.**

---

## Verification notes (vs. the original, unverified project plan)

- The plan's model *names* — "Ministral 3 3B Instruct" and "Gemma 4 E2B" — turned out to be **correct and current**, even though the plan flagged them as unverified. Both are real, currently-shipping releases (Mistral 3 family announced 2025-12-02; Gemma 4 announced 2026-04-02), confirmed directly against Hugging Face's API and the vendors' own blog posts, not taken on trust from the plan.
- The plan's Apache-2.0 licence claim for Ministral was also correct, but only **by coincidence of timing**: the *previous* Ministral generation (Ministral 8B, October 2024) shipped under the non-commercial **Mistral Research License**, which is what likely motivated the "unverified" flag. Mistral relicensed the new Ministral 3 family (3B/8B/14B, Dec 2025) under Apache 2.0. If this project is ever pinned back to an older Ministral checkpoint, the licence must be re-checked — it will not be Apache 2.0.
- Similarly, Gemma's historical licence (Gemma 1–3n) was Google's custom Gemma Terms, not Apache 2.0 — the scepticism about "Gemma 4" in the plan was reasonable. Gemma 4 specifically switched to Apache 2.0; older/cached Gemma 3n instructions elsewhere in the repo should not be assumed to carry the same terms.

## RAM budget flag

Project target (per `plans/rainverify_prototype_v0.0.1.md` §9): peak LLM RAM ≤ 1.8 GB at
2k context. Both files here are larger than the 1.5–2.5 GB range the brief anticipated:

- Ministral Q4_K_M: 2.15 GB file. At load, llama.cpp's resident memory typically runs
  somewhat above the file size once the KV cache and framework overhead are added, so
  this is likely to sit close to or above the 1.8 GB ceiling at 2k context — it is not
  a comfortable margin. Mistral's official repo does not offer anything smaller than
  Q4_K_M; a smaller quant would require a third-party requantizer (e.g. bartowski,
  unsloth) offering Q3_K_M/IQ3 (~1.6–1.7 GB), at some cost to output quality.
- Gemma 4 E2B IQ4_XS: 2.98 GB file — this is the more likely of the two to blow the
  RAM budget. The E2B "effective 2.3B" marketing figure undersells the actual on-disk
  footprint (5.1B total parameters with embeddings), so even the smallest sensible
  4-bit quant lands near 3 GB. If E2B fails the gate, the E4B variant will be worse;
  the fallback would be a lower-bit quant (Q3/IQ2 range, 2.3–2.5 GB) or reconsidering
  whether E2B is the right Gemma size for this budget at all.

Recommendation: run the Week-5 gate script (`scripts/benchmark_model.py`, peak RAM /
tokens-per-second / JSON-validity) on the reference machine against both files as
downloaded before assuming either passes. Don't block on it now — that benchmark is
exactly what the project plan already schedules for this decision — but budget time
for a second download pass at a lower quant if one or both fail the 1.8 GB ceiling.
