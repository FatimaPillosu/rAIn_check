# Brier score and Brier Skill Score (BSS)

## What it is

The Brier score (BS) verifies a probability forecast of a binary event — here, "will
24h precipitation reach or exceed X mm?" — by averaging the squared difference between
the forecast probability (the fraction of ensemble members exceeding the threshold) and
the outcome (1 if it happened, 0 if not). BS = 0 is a perfect probabilistic forecast;
BS = 1 is the worst possible. Because it is a mean of squared terms, it rewards being
close to certain (0 or 1) when you're right, and punishes being close to certain when
you're wrong, more than it punishes honest uncertainty.

BSS compares BS against a reference forecast — here, the sample climatological
probability of exceedance built from the observations themselves (plan §7). BSS = 1 is
perfect, BSS = 0 means no better than always forecasting climatology, and BSS < 0 means
worse than climatology.

## Worked example (5 numbers)

Two cases at a 10mm threshold. Forecast probabilities: 0.3, 0.7. Observed: 5mm (no), 15mm
(yes).

- Case 1: (0.3 − 0)² = 0.09
- Case 2: (0.7 − 1)² = 0.09
- BS = mean(0.09, 0.09) = **0.09**

For BSS, if the sample climatological probability of exceeding 10mm were, say, 0.5, the
climatology forecast's BS would be mean((0.5−0)², (0.5−1)²) = 0.25, giving
BSS = 1 − 0.09/0.25 = **0.64** — a real skill improvement over climatology in this toy case.

## Common misreadings

- **"BSS < 0 means the forecast is useless."** It means the forecast is worse than the
  local climatological base rate at that specific threshold — it can still contain
  useful information the reference doesn't capture (e.g. at other thresholds or leads).
- **Comparing BSS across stations without checking their climatology.** BSS is relative
  to each case's own reference, so a BSS of 0.3 at a very dry station and 0.3 at a very
  wet station reflect different absolute skill levels — don't average BSS across
  stations with very different base rates without weighting by sample size.
- **Trusting BSS from a small sample.** rAIn_check flags any BSS computed from fewer than
  30 pairs — with fewer cases, the climatological reference itself is poorly estimated,
  and the BSS number can swing wildly.

## Reading it for rainfall

Choose thresholds that mean something operationally (light rain, heavy rain, flood-risk
rain), not just round numbers — rAIn_check's defaults (1, 5, 20, 50 mm/24h) are a
reasonable spread across "any rain" to "heavy rain" but should be adjusted to match local
impact thresholds where known. BSS at a high threshold (50mm) will usually be noisier
than at a low threshold (1mm) simply because exceedances are rarer — check the sample
count, not just the BSS value.
