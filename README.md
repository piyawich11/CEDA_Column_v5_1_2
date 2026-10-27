# CEDA RC Column Design – Streamlit v5.1

**v5.1 (27 Oct 2026) – look of the UI mock-ups, design and engine unchanged (skill v1.5.0):** light theme locked in
`.streamlit/config.toml` (no longer follows Windows / browser dark mode), IBM Plex fonts, navy sidebar with numbered steps
(green done · amber needs a decision · blue current) and a project box, white cards, file rows "✓ read · name · Replace · Remove",
model routing table on step 1, case table with grouped headers and the f'c strip on step 4, story pills on the fix board,
Table of Column as a mark × range grid on step 7, file table on step 8, "Next →" at the bottom of every step.
Presentation only: `ui.py` (CSS + helpers). Streamlit ≥ 1.60 (tested 1.66). On Streamlit Cloud keep `.streamlit/` next to `app.py`
at the repository root.


Front end for the **ceda-column-design** skill (v1.5.0). `engine/ceda-column-design/` is the skill folder, unchanged; the app calls
its scripts and never re-implements a design rule. To update: replace `engine/ceda-column-design/` with the new skill folder and run
the tests.

## Run
```bash
pip install -r requirements.txt
python3 tests/test_app.py "<BKMPH02 folder>"      # must print ALL PASS (without the folder: A + B only)
python3 tests/at_flow.py "<BKMPH02 folder>"       # whole flow 1 → 8 with Streamlit AppTest (~8 min)
streamlit run app.py
```

## What changed from v4
| v4 | v5 (skill v1.5.0) |
|---|---|
| size_restricted list decided which columns may use ρ 6–8 % | removed – every column is designed at its input size (ρ ≤ 6 %) until the fix board; ρ 6–8 % approved per column there (Approve_rho pre-selected, applied only with Apply) |
| ρ with approval fixed at 8 % | adjustable 6–8 % (default 7 %, ACI 318-19 §10.6.1.1); **SMF locked at 6 %** with a red note (§18.7.4.1) |
| f'c scenarios S0 / S10 / S25 | **case table**: case A/B per development-table f'c (up to 700), limits 10/15/20/25 %, failing split (ρ 6–8 / enlarge / never), f'c-overstrength, low D/C %, m³ high/typical, main bars t, cost (info) |
| fix board: preview one change | per-row actions: approve ρ, **enlarge** (option 1 range row / option 2 down to the lowest story; proposals within the section below first, then short/long/ratio or diameter; target D/C ≤ 0.90), **accept overload** (tick per row, engineer name once at the top); splice override per column |
| enlarged sizes stayed "check with ETABS" | **6 Final check** on one page: rounds, ETABS update list, new exports, section match, old vs new compare, fix again, **Mark FINAL** (optional mark renumber by size + rename table) or continue PROVISIONAL |
| results | 7 Results: column detail (interactive surface + to-scale section with bars, bundles, hoops), checks, small column plan |
| splices | project default on page 2 (Lap – staggered / Lap – one level / Mechanical coupler) + per-column override |
| mark names changed every run | locked after the f'c case; new groups appended (C31 …); renumber only at FINAL |

## Steps
1. **Files** – seismic, full gravity (unreduced), full reduced (optional), load combinations, development-length table, input workbook.
2. **Inputs** – criteria (incl. ρ max with approval, splice method, fix.*, fc.*), stories, sections, combos, lap, prices.
   A v1.3.6/v1.4 workbook runs with v1.5 defaults for the missing keys (flagged on page 3).
3. **Check & run** – routing, ✔/✖ list, run + f'c case study (approvals ignored in the study).
4. **f'c study** – case table, recommended per limit; "Use this case" runs the project with that f'c and locks mark names.
5. **Fix board** – failing columns grouped per label: ρ 6–8 % / enlarge / accept overload; δ > 1.4 rows; Apply all → one run.
6. **Final check** – A old forces · B ETABS update xlsx · C upload new exports · D compare · E fix · F FINAL / provisional.
7. **Results** – Table of Column, decisions, quantities, notes, column detail, column plan.
8. **Documents** – decisions log, input workbook used, ETABS update list, Mark rename table; on request calc PDF, back-up Excel,
   Table of Column DXF/PDF, schedule (PROVISIONAL stamped until FINAL).

## Tests
- `tests/test_app.py`: A skill self-test · B app == skill CLI, documents on request, project round trip · C BKMPH02: fixed f'c ==
  final run (1,277 label-stories), f'c cases (600/3F 9 failing; recommended 500/1M at 10 %, 450/1M at 15–25 %), fix-board
  preview and proposals C75 B2, only confirmed overload applied, quantities + cost.
- `tests/at_flow.py`: AppTest flow 1 → 8 on BKMPH02 (study, case, fix board proposals + Apply, final check rounds, FINAL).

## Not covered (same as the skill)
Sway frames (δs), SMF detailing, joint shear, L-shaped columns, spiral φ. Outputs are drafts for engineer review.
