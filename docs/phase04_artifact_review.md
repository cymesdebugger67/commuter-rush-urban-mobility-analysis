# The Commuter Rush — Phase 04 Review Assessment

- **Project author:** Cyril James Lunzaga
- **Review date:** November 16, 2026
- **Reviewed source:** User-supplied `phase04_review_bundle.zip`
- **Bundle SHA-256:** `235322440ea3321fb8cda73bf7d1e8f6e93e9869cba1b1b945552890bd71453d`

## Decision

**APPROVE Phase 04 artifact and visual signoff, with required release follow-ups.** The review archive's numerical tables, saved fingerprints, reports and nine plots are internally consistent. This is **not** a full source-code or raw-file audit: the review ZIP contains neither the implementation modules nor the 310,187-row processed source CSV. The user's terminal previously reported that 58 automated tests, the source-linked verifier and the source-data hashing passed.

## Completed checks

- Inspected all 17 CSV tables, nine PNG figures, two Markdown reports and six JSON manifests/summaries in the uploaded archive.
- Verified all **35 references** to table, figure, and report content against their SHA-256 fingerprints and tabular row counts: **0 mismatches**.
- Reconciled estimated entries across daily, borough and day-type tables: **114,680,137**.
- Recomputed the mean across weekday day-pair rows of evening minus morning share: **+3.07994 percentage points**; all **23/23** weekdays were positive.
- Recomputed four borough-level day-pair means and the paired Manhattan-versus-pooled-outer-borough contrast: **+27.60728 percentage points**.
- Recalculated station orientation distribution: **261 morning-oriented; 91 evening-oriented; 72 balanced**, covering **424** station complexes.
- Recalculated category stability under the alternative peak window: **377/424 = 88.9151%**; validated labels against the stated ±0.15 balance-index threshold.
- Confirmed all 424 station records in the supplied orientation table meet their **peak-window**, not necessarily all-day, observed-hour threshold.
- Inspected the nine rendered figures. The borough peak-share legend no longer overlaps its bars. No material clipping or misleading graphic encodings observed. The highest-volume-station plot uses ellipses for some long station names; the full names remain in the source tables.

## Supported findings

- Weekday mean daily estimated entries **4,128,695.74**, versus weekend mean **2,465,016.88**; observed ratio **1.6749**. Reported within-month calendar-day bootstrap interval **[1.5357, 1.8330]**.
- Reported day-level average evening-minus-morning difference **+3.0799 percentage points**, interval **[+2.4387, +3.8422]**.
- Manhattan's weekday entry shares: morning **16.50%**, evening **31.72%**. Brooklyn, Bronx and Queens have larger morning than evening shares, showing a borough-level asymmetry.
- Of Manhattan's **121** eligible station complexes, **74** are evening-oriented; of the **303** eligible station complexes in the Bronx, Brooklyn and Queens, **237** are morning-oriented.
- **10,508** station-hours have recorded source coordinate variants, retained as audited metadata disagreements rather than silently discarded or treated as distinct station-hour records.

## Required follow-ups before public release

1. **Calendar-day dependence and month scope.** Keep statistical intervals explicitly labeled as within-month day-resampling intervals, not universal population confidence intervals, causation, ridership forecasts, or long-run seasonality. The inferential basis (10,000 bootstrap replications, fixed seed 202410, calendar-day unit, and percentile/other interval method) should be clear in methods documentation. The review archive includes the replication count and seed, but not the bootstrap implementation source.
2. **Holiday / unusual-weekday sensitivity.** October 14 has **3,104,249** estimated entries, the month's lowest observed weekday, **24.81% below** the mean weekday total. Analyze whether excluding that date changes the weekday/weekend ratio or evening-minus-morning day-level estimates; do not assume the cause without external corroboration.
3. **Station typology transparency.** Explain orientation as a rule-based classification from entry-window balance index with a conventional ±0.15 cutoff, not observed travel direction, station function, or unsupervised machine-learning clusters. Emphasize that **47/424** station labels change under the tested alternative four-hour windows.
4. **Coverage and spatial claims.** The 90% station eligibility test concerns predeclared weekday peak-hour coverage. Whole-system hourly station reporting varies, so no missing station-hour should be silently treated as zero; representative coordinates are not authoritative station locations.
5. **Dependency maintenance.** Address non-blocking NumPy/pandas timedelta deprecation warnings before publication, then rerun all tests and regenerate affected figures. Review chart filenames, git-ignore behavior, provenance, usage terms, notebook outputs, and public attribution.
6. **Full-code and Git review.** Audit the actual local Python modules, source manifest, notebooks and release file list prior to commit/push. The Phase 04 review ZIP alone cannot establish these facts.

## Portfolio decision

Move into **Phase 05 integrated narrative and reproducibility** without adding optional clustering. The borough reversal and station-versus-systemwide paradox already give the project a coherent, evidence-grounded central story. Add a short outlier sensitivity table, well-scoped reproducible notebook(s), a clear README and original visual identity, and final release security checks before publishing.

**Signoff scope:** Phase 04 *numerical artifact consistency and visual presentation* approved. **Full repository release** pending the above follow-ups.
