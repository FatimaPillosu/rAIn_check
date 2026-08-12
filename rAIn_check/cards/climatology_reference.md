# Climatology reference

## What it is

Skill scores like BSS need something to be skilful *relative to* — otherwise a score
just says "the forecast has some error", not "the forecast is worth having". rAIn_check
builds that reference from the observation series itself (plan §7): the sample
climatological probability of an event is simply the fraction of observed days in the
dataset that exceeded the threshold. There is no external climate normal, no
model-based reference — the yardstick comes entirely from the same station data being
verified, which is deliberate: it keeps the reference honest for whatever period and
location is actually being analysed, without needing a long external climate record
the demo/partner dataset may not have.

## Worked example (5 numbers)

Five observed days at a 10mm threshold: 15, 2, 0, 12, 3 mm. Two of the five (15 and 12)
reach or exceed 10mm.

Climatological probability = 2/5 = **0.4**

Every case in the sample is then compared against a "forecast" that always says 40% —
this is what BSS measures skill against.

## Common misreadings

- **"Climatology" here means a long-term official climate normal.** It doesn't — it's
  the sample climatology of whatever observation series is loaded, which could be a
  demo pack spanning weeks, not decades. A short or unusual period gives a
  correspondingly unreliable reference.
- **The same climatology probability applies everywhere.** rAIn_check's default builds
  one pooled probability from all stations/dates in the current dataset; a station in a
  wet microclimate and one in a dry one share the same reference unless stratified
  separately, which will understate BSS at the wet station and overstate it at the dry
  one.
- **A high BSS proves genuine forecast skill beyond the local rainfall pattern.** It
  proves skill relative to *this* dataset's own base rate — useful, but not the same
  claim as skill relative to a robust long-term climate normal.

## Reading it for rainfall

Because rainfall's climatological probability changes sharply with threshold (light rain
might occur 40% of days, 50mm+ rain perhaps 2%), always check which threshold's BSS
you're looking at before comparing skill across thresholds — a small absolute
improvement in probability estimation matters far more, proportionally, at a rare
high-impact threshold than at a common low one.
