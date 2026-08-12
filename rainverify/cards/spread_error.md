# Spread-error ratio

## What it is

An ensemble's spread (how much its members disagree with each other) should, on
average, match how wrong its mean forecast actually turns out to be (the RMSE of the
ensemble mean against observations). The spread-error ratio divides the two:
spread ÷ RMSE. A ratio near 1 suggests the ensemble's own uncertainty estimate is
trustworthy on average. A ratio well below 1 means the ensemble is under-dispersive
(overconfident — real errors are bigger than the spread admits). A ratio well above 1
means over-dispersive (the ensemble hedges more than it needs to).

rAIn_check computes spread as the mean, across all pairs, of each pair's ensemble
standard deviation (sample standard deviation across members, not population), with no
finite-ensemble-size correction applied — some verification literature applies an
inflation factor of sqrt((M+1)/M) to account for a finite number of members
under-sampling the true spread; this build uses the plain, uncorrected definition, noted
here rather than silently chosen.

## Worked example (5 numbers)

Two forecast-observation pairs. Pair 1: members 1, 2, 3 mm, observation 2mm. Pair 2:
members 4, 5, 6 mm, observation 4mm.

- Ensemble means: 2, 5. Errors: 0, 1. RMSE = sqrt((0² + 1²)/2) = sqrt(0.5) ≈ **0.707**
- Ensemble std (each pair): std(1,2,3) = 1.0, std(4,5,6) = 1.0. Spread = mean(1, 1) = **1.0**
- Ratio = 1.0 / 0.707 ≈ **1.414** (over-dispersive in this toy example)

## Common misreadings

- **This is a single-case diagnostic.** It is a sample-average statistic; a ratio near 1
  can hide individual cases that are badly under- or over-dispersive in opposite
  directions and cancel out. Look at the rank histogram alongside it for the fuller
  picture.
- **Ratio > 1 is always worse than ratio < 1.** Under-dispersion (< 1) is usually the
  more operationally dangerous failure mode, because it means confident-looking
  forecasts are missing real risk more often than they admit.
- **A good ratio proves the ensemble is skilful.** It says the uncertainty estimate is
  self-consistent, not that the forecasts are accurate — a very wide, very wrong
  ensemble can still have spread ≈ error.

## Reading it for rainfall

Spread naturally grows with lead time as forecast uncertainty compounds; rAIn_check
reports this ratio per lead day so growth in spread can be checked against growth in
actual error, rather than looking at a single pooled number across all leads.
