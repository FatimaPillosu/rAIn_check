# Rank histogram

## What it is

For each forecast-observation pair, find where the observation ranks among the sorted
ensemble members (below all of them, between two of them, or above all of them), then
histogram those ranks over many cases. If the ensemble is statistically
indistinguishable from reality — the observation is "just another member" — the ranks
should be uniformly distributed: no rank is more likely than any other. rAIn_check
reports the rank counts alongside a chi-square flatness test (higher chi-square /
lower p-value = stronger evidence against flatness).

This is a calibration check, not a skill score: a flat rank histogram means the
ensemble spread is trustworthy, not that the forecasts are accurate.

## Worked example (5 numbers)

Ensemble: 1, 2, 3, 4 mm (M = 4 members, so 5 possible ranks: 1 to 5).
Observation: 2.5 mm.

The observation falls strictly between the 2nd and 3rd sorted members, so it gets
**rank 3**. Over many such cases, tally how often each rank (1 through 5) occurs and
compare the shape to a flat line at (total cases) / 5.

## Common misreadings

- **U-shaped histogram = "bad forecast".** It specifically means under-dispersion: the
  ensemble is too narrow, so the truth too often falls outside it (at the extreme
  ranks). The ensemble-mean forecast itself can still be skilful.
- **Dome-shaped (peaked in the middle) histogram = "good forecast".** It means
  over-dispersion: the ensemble spread is too wide, so the truth clusters in the middle
  ranks more than it should. rAIn_check's own golden dataset produces a dome shape by
  construction — its synthetic ensemble spread was deliberately generated wider than
  the "station representativeness" noise added to observations.
- **A slanted (asymmetric) histogram is about spread.** It usually indicates bias, not a
  spread problem — the ensemble is systematically too high or too low, not too narrow
  or too wide.

## Reading it for rainfall

Ties are common with rainfall (many members forecasting exactly 0mm on a dry day), and
ties are broken at random when computing ranks (a fixed seed keeps this reproducible run
to run). A rank histogram built mostly from dry-day ties says little about calibration
during rain events — for operational use, consider building separate rank histograms for
wet days only (obs > 0mm) alongside the all-days version.
