# tests – fixtures and correct values

`scripts/selftest.py <skill folder>` reads `expected.json` and the files in `fixtures/` and must print **ALL PASS**.

| file | what | source of the correct value |
|---|---|---|
| `expected.json` | every value the self-test asserts, grouped T1–T13, each with its `_source` | see table below |
| `fixtures/c1_forces.json`, `c1_config.json` | VOCO C1 loads (normalised from the issued Excel load sheets 03_01_01…06) + confirmed criteria | CEDA Excel calc |
| `fixtures/make_synthetic_etabs.py` | 4-story synthetic ETABS set (seismic / full reduced / full unreduced) | hand check |
| `fixtures/voco_column_load.xlsx` | VOCO ETABS export, Element Forces only (1st–20th) | ETABS |
| `fixtures/voco_load_combination_headerless.xlsx` | VOCO combo definitions pasted without header | ETABS |
| `fixtures/voco_input_workbook.xlsx` | CEDA input workbook filled for the VOCO test (sizes 450×2000 and Lu 4.5 m are test values) | designer test input |
| `fixtures/paattern.dxf` | CEDA bundle / inner-bar pattern (1100×900 and 900×900, DB32) drawn by the designer | CEDA drawing 20 Oct 2026 |
| `bkmph02_regression/` | BKMPH02 first real project: every column-story result v1.3.4 + decisions log (record, not asserted) | engine v1.3.4 + designer decisions |
| `voco_regression/` | engine v1.2 vs issued drawing S-04-01-01 R3 for C1–C12 (27 rows), CSV + Excel + side-by-side PDF | issued drawing + CEDA Excel |

| group | checks | source |
|---|---|---|
| T1 | grid c/c 125–150, small-face count, symmetric ties, tie-corner ladder, 1 % pattern | CEDA rules, C1 hand sketch |
| T5 | small-face bar count 2/3/4, clear spacing drop, 3-bar face tie | CEDA rule 19 Oct 2026, ACI 25.2.3 / 25.7.2.3 |
| T2 | C1 VOCO design per row (bars, D/C, δ) | engine baseline (regression lock) |
| T8 | issued C1 bars on the drawn grid check D/C ≤ 1 where Lu/k equal the issued calc | issued drawing S-04-01-01 R3 |
| T3 | ETABS reader, combo check ข้อ 7, basement P / M / V, βd | hand check |
| T4 | common story ranges | CEDA rule |
| T6 | marks: rotation, ties in the mark, envelope criterion A (≤ 25 % per label, ≤ 10 % project) | CEDA rules 19 / 20 Oct 2026 |
| T9 | wider grid c/c ≤ 160 for 3–4-bar bundles, circle ties | CEDA 20 Oct 2026, ACI 25.2.3 / 25.6.1.6 hand check |
| T10 / T10b | inner bars at the tie crossings – engine positions and the fixture drawing itself | paattern.dxf (CEDA, 20 Oct 2026) |
| T11 | engineer-accepted overload status (ACCEPTED / REVISE / OK) | CEDA 21 Oct 2026 |
| T12 | ETABS sheet without its TABLE: row; overload gate (--overload-confirmed) | CEDA 21 Oct 2026 |
| T13 | column mapping plan (plan_map.py): every column placed with mark + label, PDF + DXF | synthetic points on the T7 run |
| T7 | Excel input path: forces only → missing list → input workbook → config → run | designer test input |

**Re-baselining** (T2 / T7 numbers) is allowed only after a rule change agreed with the designer; note the change in the
SKILL.md change log and in `_source`. T3 / T8 values come from hand checks or the issued design and must not be re-baselined –
exception recorded 21 Oct 2026: T8 4th-10th 44-DB28 now uses 2-bar bundles at all 22 drawn positions (as on the issued drawing; the
old ladder put 3-bar bundles at the corners), D/C 0.858 → 0.880, still ≤ 1. `voco_regression/` is the v1.2 record (before the
bundle-order rule); rerun it before relying on it for v1.3.4+.

- T14 (v1.3.6): lap reader on `fixtures/lap_table_TABLE_11_04.xlsx` (BKMPH02 TABLE 11.04, sheet 40mm) against the Lap sheet of the
  BKMPH02 input workbook; Story_ranges round trip + coverage check; `fixtures/bkmph02_load_combination.xlsx` merged per combo
  (0.9 DL stays 0.9); unreduced model promoted. BKMPH02 rerun from the raw files with v1.3.6 = v1.3.4/1.3.5 record (0 differences).
- T15 (v1.4.0): f'c study on a hand-built matrix – S0 / S10 / S25 / recommended per the CEDA rule of 23 Oct 2026, D/C floor with the
  typical-f'c minimum-steel exemption, quantities and cost (hand calculation in expected.json), FALLBACK when no scenario fits.
  BKMPH02 (real project): fixed f'c run identical to v1.3.4–1.3.6 (1,277 label-stories); auto study: S0 700/3F, S10 500/1M,
  S25 450/1M (recommended by the rule) – with the example prices the 600 ksc scenarios are cheapest (designer decides).
- T16 (v1.4.0): quick_check of an unchanged column = the run (status, D/C); a larger section lowers D/C and flags the ETABS forces.
