# CRPS (Continuous Ranked Probability Score)

## What it is

CRPS measures how close an ensemble forecast's probability distribution is to a single
observed value, in the same units as the variable (mm/24h here). It reduces to the
absolute error when the ensemble has no spread (a deterministic forecast), and rewards
both accuracy (the ensemble centred on the right value) and sharpness (a tight,
confident ensemble) — but only sharpness that is honest: an overconfident ensemble that
misses is penalised more than a wider, well-calibrated one. Lower is better; CRPS = 0
is a perfect deterministic hit.

rAIn_check computes CRPS exactly via the Hersbach (2000) interval method — no Monte
Carlo approximation — by summing, over each gap between sorted ensemble members, a
term that depends on where the observation falls relative to that gap.

## Worked example (5 numbers)

Ensemble members: 1, 1, 3, 3, 5 mm. Observation: 3 mm.

Sorted members split the number line into intervals. The observation (3) sits exactly
on two repeated members, so several intervals contribute nothing (zero width). Working
through the Hersbach formula interval by interval gives:

CRPS = 0.4 mm

(Verified two ways in this codebase: by hand, and by cross-checking against the
independent `properscoring` package to 1e-6 — see `tests/test_engine/test_scores.py`.)

## Common misreadings

- **"CRPS in mm, so I can compare it across variables."** No — like MAE, its units match
  the variable, so a CRPS of 2mm for rainfall is not directly comparable to a CRPS of
  2°C for temperature.
- **"A single CRPS number tells me if the ensemble is well calibrated."** No — CRPS
  bundles resolution and reliability together (rAIn_check's `crps_decomposition` splits
  these where possible; see that function's docstring for a confidence note on which
  part is fully verified). A rank histogram tells you about calibration specifically.
- **"Lower CRPS always means a better forecast for my use case."** Not necessarily — CRPS
  is an average over the whole distribution; a forecaster mainly interested in whether a
  damaging threshold is exceeded should look at the Brier score/BSS at that threshold too.

## Reading it for rainfall

Rainfall is right-skewed and has a spike of probability at exactly zero (dry days), which
makes CRPS harder to interpret than for a smooth variable like temperature: a forecast
that is "close" on a dry day (small ensemble spread near zero) can look deceptively good.
Always read CRPS alongside the rank histogram and BSS at a meaningful rain/no-rain
threshold, not on its own.
