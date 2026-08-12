# Reliability diagram

## What it is

A reliability diagram checks whether a forecast probability means what it says: among
all the times the ensemble said "70% chance of exceeding 20mm", did that threshold
actually get exceeded about 70% of the time? Forecast probabilities are grouped into
bins (rAIn_check uses 10 bins: 0-10%, 10-20%, ..., 90-100%); for each bin, plot the mean
forecast probability against the observed frequency of the event in that bin. Points on
the diagonal are perfectly reliable. A companion sharpness histogram (how many cases
fall in each probability bin) shows whether the forecast is ever confident at all — a
forecast that always says "50%" can be perfectly reliable and still useless.

## Worked example (5 numbers)

Five cases all land in the 60-70% probability bin, with forecast probabilities 0.61,
0.63, 0.65, 0.68, 0.69 (mean ≈ 0.65) and outcomes 1, 1, 0, 1, 0 (observed frequency =
3/5 = 0.6). That bin's point plots at (0.65, 0.6) — close to the diagonal, so reliable
in this bin, though five cases is far too few to trust (rAIn_check flags any bin with
fewer than 30 cases).

## Common misreadings

- **A point above the diagonal means "the forecast is good".** It means the forecast is
  under-confident in that bin (events happen more often than the stated probability) —
  correctable, but not automatically "good"; a forecast that only ever issues 50% and is
  always right 50% of the time is reliable and useless.
- **A point below the diagonal means "the forecast over-warns".** Correct direction, but
  check the sample count first — a single bin with 8 cases can sit anywhere by chance.
- **Judging the whole forecast from one bin.** Read the full curve's shape (an S-curve
  around the diagonal is classic under-confidence at the extremes) together with the
  sharpness histogram underneath it, not any single point.

## Reading it for rainfall

Rainfall forecasts are usually sharpest (most confident, near 0% or 100%) at low
thresholds like "any rain" and much less sharp at high thresholds like "50mm+", simply
because heavy-rain ensemble members disagree more. Expect the sharpness histogram to
thin out toward the high-probability end as the threshold increases, and treat any
high-probability bin with a handful of cases as informative but not yet trustworthy.
