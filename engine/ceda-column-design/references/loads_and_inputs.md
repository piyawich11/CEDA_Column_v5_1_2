# Loads and inputs (engine: etabs_io.py, prepare_inputs.py, input_workbook.py)

## 1 ETABS exports (one workbook per model is fine – every `TABLE:` block is read)
| # | model | tables |
|---|---|---|
| 1 | seismic model (above ground, reduced stiffness) | Element Forces – Columns (EQ combos incl. V2/V3), Load Combination Definitions, Column / Point Object Connectivity, Frame Assignments – Section Properties, Concrete Rectangular / Circle, Story Forces, Story Drifts |
| 2 | full model, reduced stiffness | gravity combos + load cases DL/SDL/LL, connectivity, sections |
| 3 | full model, unreduced stiffness | gravity combos |
Units from the units row (tonf / kN / kgf; m / mm / cm). P negative in compression → +compression, tension kept (sign kept – designer).
Axis mapping b = t2 (M2 → My), h = t3 (M3 → Mx). Section from the name `C 2000x450` = t3 × t2 only when no section table – **Assumption**.

## 2 Load combinations – กฎกระทรวง พ.ศ. 2566 ข้อ 7 (SDL counted as dead) – **Code**
| kind | expected factors |
|---|---|
| gravity | 1.4 D + 1.7 L |
| seismic | 0.75(1.4 D + 1.7 L) + 1.0 E  or  0.9 D + 1.0 E |
| wind | 0.75(1.4 D + 1.7 L) + 1.6 W  or  0.9 D + 1.6 W |
Kind and factors come from the combo definitions (nested combos resolved), **never from the name**; every mismatch is listed – ask:
include or `exclude_combos`. Step Type Max/Min kept as separate rows. Gravity case names are configurable (Criteria gravity.DL/SDL/LL).

## 3 Load assembly – CEDA Rev.1 – **Practice**
- Gravity part: gravity combos of the full model, reduced **and** unreduced stiffness.
- Seismic part above ground: EQ combos of the seismic model (its gravity combos dropped).
- Basement (stories in the full model below the seismic model), every EQ combo:
  P = P at the base of the lowest above-ground column (seismic model) + Σ factor × [P_case(this basement column bottom) − P_case(lowest above-ground column bottom)], cases DL/SDL/LL of the reduced full model;
  M, V = larger of the value carried down from the lowest above-ground column (pinned base) and Σ factor × gravity value.
- Columns matched by label + XY (unique names may differ). Story order by elevation.
- Story naming: ETABS story N = column below level N; drawing level = from the level below to N (both shown).

## 4 CEDA input workbook (`assets/CEDA_Column_Input_TEMPLATE.xlsx`; reader `scripts/input_workbook.py`)
| sheet | columns | becomes |
|---|---|---|
| Criteria | key, value, unit, note | config (project, seismic, materials, detailing, slender, gravity names, marks, story ranges) |
| Stories | story, z_bottom_m, z_top_m, basement, Lu_m, k, fc_ksc | story order, connectivity length, per-story overrides, basement list, fixed f'c |
| Columns | label, story, x_m, y_m, Lu_m, k | Column/Point Object Connectivity per column-story, per-column overrides |
| Sections | label, story_from, story_to, shape, b_mm, h_mm | Frame Assignments + section definitions |
| Combos | combo, \<load case\> … | Load Combination Definitions |
| Lap | fc_ksc, DB12 … DB32 | lap_table |
| Exclude / Approve_rho | combo / label, story | exclude_combos / approved_rho_over_6 |
| Accept_overload / Accept_delta | label, story, dc_max / delta_max | accept_overload (applied only with `--overload-confirmed` after asking the designer in the session) / accept_delta – Engineering judgment, reported |
| Enlarge (v1.5.0) | label, story_from, story_to, shape, b_mm, h_mm, option | section_overrides (fix board; PROVISIONAL until the ETABS export has the size) |
| Splice (v1.5.0) | label, story_from, story_to, method | splice_by (default Criteria detailing.splice) |
| Marks (v1.5.0) | label, mark | mark_names (locked after the f'c case; new groups appended; renumber at FINAL) |
Criteria v1.5.0: detailing.rho_max_pct 6, detailing.rho_ask_pct 7 (6–8, SMF 6), detailing.splice, fix.target_dc 0.90, fix.step_mm 50,
fix.max_add_mm 500, fix.compare_ddc 0.05, marks.renumber, fc.limits_pct, fc.max, fc.dc_low, fc.exempt_rho_pct. A v1.3.6/v1.4 workbook
without these keys runs with the defaults (listed as missing keys). Removed: detailing.size_restricted, fc.outlier_pct / outlier_max_pct.
Merge rule: the workbook wins **per item** – sizes per label-story (story_from/to), connectivity per column-story, factors per combo; other items keep ETABS;
every replacement is reported. Without XY the models are matched by label only.
`prepare_inputs.py` writes `config.json`, normalised model workbooks and `input_check.json` (✔/✖ per input); exit 2 when something is missing.


## v1.3.6 – file set and routing (BKMPH02)
| upload | use |
|---|---|
| seismic model | above-ground EQ combos, sway Q |
| full model – gravity / unreduced | gravity combos; **primary full model when no reduced model is given (ASSUMPTION, reported)** |
| full model – reduced stiffness (optional) | primary full model (geometry, DL/SDL/LL cases for βd and the basement ΔP) – Rev.1 |
| Load Combination Definitions file | merged into every model; its combos replace the ETABS definitions of the same name |
| CEDA TABLE 11.04 (development length) | Lst (Class B tension lap, other bar) per f'c and bar → Lap sheet when the workbook has none |
| input workbook sheet Story_ranges | story ranges fixed by the designer; must cover every story once (checked) |
