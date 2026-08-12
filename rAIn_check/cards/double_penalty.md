# Double penalty

## What it is

The double penalty is a well-known failure mode of point-to-point (or grid-to-station)
verification: when a forecast gets a rain feature's intensity right but its
location or timing slightly wrong, standard scores punish it twice — once for
forecasting rain where none was observed (a "false alarm" at the displaced location),
and again for missing the rain where it actually fell (a "miss" at the true location).
A forecast that is nearly perfect but shifted 25km or three hours can score worse, on
CRPS, Brier score, or any of the point-based scores in this system, than a much cruder
forecast that simply predicts widespread light rain everywhere.

This is not a bug in any individual score — it's a structural property of comparing a
spatially/temporally precise forecast field to point observations one location at a
time, which is exactly what rAIn_check's nearest-grid-point matching does (plan §7).

## Worked example (5 numbers)

Consider a rain band forecast to bring 20mm to a station, but observed 20mm one grid
cell away instead. At the forecast's location: forecast = 20mm, observed ≈ 0mm (a large
error). At the true location: forecast ≈ 0mm, observed = 20mm (an equally large error).
Both points are individually "wrong" even though the forecast correctly predicted a
20mm rain band existed, just shifted — a single, small displacement error is counted
as two separate errors.

## Common misreadings

- **"A bad score here means the model has no skill."** It may mean the model has a
  displacement error, which is a real but different problem from having the wrong
  intensity or no signal at all — worth distinguishing before concluding a forecast is
  unusable.
- **"This means point verification is wrong and shouldn't be used."** Point verification
  is still the right tool when the question is "how good was the forecast at this
  specific station" (which is what most partner institutions need for warnings at named
  locations) — the double penalty is a reason to interpret scores carefully, not a
  reason to discard them.
- **Assuming neighbourhood/fuzzy verification (spatially tolerant scoring) automatically
  fixes this.** It reduces the double penalty by design, but is not implemented in this
  prototype — nearest-grid-point matching only. Worth flagging as a capability request
  (plan §8.2, Level 3) if displacement errors are a recurring concern.

## Reading it for rainfall

Convective rainfall (localised, sharp-edged storms) is far more prone to the double
penalty than widespread frontal/monsoonal rain, because small position errors move the
storm off the verification point entirely. If CRPS or BSS look surprisingly poor for a
period known for convective activity, check the maps & case studies step before
concluding the ensemble itself lacks skill — a shifted-but-present rain feature is a
different diagnosis from a genuinely missed event.
