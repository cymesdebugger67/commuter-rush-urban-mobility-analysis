# Phase 05 — interpretive story and pending release checks

**Author:** Cyril James Lunzaga

## Core research claim

The *systemwide* October 2024 weekday evening entry share exceeds its morning share, but a majority of *individual* station complexes qualify as morning-oriented. This is consistent with the higher volume weight of the large Manhattan evening-oriented stations. It is a demand distribution contrast, not direct evidence of directional passenger journeys.

## Evidence checkpoints

- 310,187 observed station-hours; 424 complexes; 114,680,137 estimated entries, October 1–31, 2024.
- Systemwide weekday peak shares: 22.8761% morning (07–09) and 25.8434% evening (16–18); weekday daily mean difference +3.0799 percentage points.
- Weekday/weekend mean estimated daily entry ratio 1.6749 (reported within-month bootstrap interval 1.5357–1.8330).
- Manhattan aggregate weekday morning 16.50%, evening 31.72%. Station orientation: 261 morning, 91 evening, 72 balanced (threshold +/-0.15). Changing peak windows alters 47/424 labels.
- 10,508 station-hours had conflicting coordinate variants, audited and reconciled. Missing records were never automatically zero-filled. Across systemwide clock hours, reporting complexes range from 387 to 424.

## Completed sensitivity and interpretive guardrails

The completed Phase 05 sensitivity retains all October days as primary and excludes October 14 only in an alternative calculation: the weekday/weekend mean ratio changes from 1.6749158 to 1.6938065; the daily evening-minus-morning share difference changes from +3.0799438 to +2.8585334 percentage points. Sample sizes are 23 weekdays/8 weekend days and 22 weekdays/8 weekend days, respectively; neither the date nor its source records were deleted. No cause is inferred. The primary analysis remains the complete October month. Intervals are within-month day-resampling estimates with finite sample/dependence limitations.

Do not claim that these estimates measure ridership boardings, train crowding, queue length, commuter destination, MTA capacity, delay, or fare-policy effects. Do not infer long-run weekday patterns beyond the one studied month.

## Before GitHub publication

1. Execute sensitivity checks and all unit tests, inspect notebook execution in VS Code.
2. Address timedelta warnings in a controlled, reproducible code change; regenerate relevant images and verify saved fingerprints.
3. Finalize root README, diagram or original cover, research narrative, and source attribution.
4. Check code against its documentation, remove prototype claims, confirm public author credit, inspect all tracked files and `.gitignore`.
5. Stage intentionally, review `git diff --cached`, commit on the research branch, push only after release approval, and merge carefully into main.
