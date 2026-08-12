# ROC curve and AUC

## What it is

The ROC (Relative Operating Characteristic) curve asks a different question from the
reliability diagram: not "does the forecast probability mean what it says", but "if I
pick some probability cut-off and issue a yes/no warning above it, how good is that
warning at separating events from non-events?" For each possible probability cut-off, it
plots the hit rate (probability of detection — fraction of real events correctly warned)
against the false-alarm rate (probability of false detection — fraction of non-events
incorrectly warned). AUC (area under the curve) summarises this in one number: 1.0 is
perfect discrimination, 0.5 is no better than a coin flip, below 0.5 means the forecast
is discriminating in the wrong direction.

Crucially, ROC/AUC does not care whether the forecast probabilities are calibrated —
only whether higher forecast probabilities correspond to a genuinely higher chance of
the event. A forecast can have excellent AUC and poor reliability (e.g. it always says
"90%" when it means "60%") at the same time.

## Worked example (5 numbers)

Forecast probabilities: 0.1, 0.2, 0.8, 0.9. Outcomes (exceeded 10mm?): no, no, yes, yes.
The forecast ranks the two events above the two non-events perfectly — however the
cut-off is chosen, the ranking never puts a non-event above an event. This gives
**AUC = 1.0** (verified directly in `tests/test_engine/test_scores.py`).

## Common misreadings

- **High AUC means the probabilities are well calibrated.** No — see above. Check the
  reliability diagram separately.
- **AUC near 0.5 means the ensemble has no information.** It means the *ranking* has no
  information at that threshold specifically; the same ensemble might discriminate well
  at a different threshold.
- **Comparing AUC between two very different sample sizes or event rates as if they were
  the same measurement.** AUC is fairly robust to base rate, but very small samples
  (few exceedance events) give a noisy, unstable curve — check the underlying case count.

## Reading it for rainfall

AUC is a useful complement to BSS precisely because it separates "can this ensemble tell
heavy-rain days from ordinary days at all" (AUC) from "does the ensemble know its own
confidence level" (reliability/BSS). A forecast with good AUC but poor BSS is often
fixable by recalibration (adjusting probabilities without touching the underlying
ensemble); a forecast with poor AUC at a given threshold usually needs a better model or
more members, not recalibration.
