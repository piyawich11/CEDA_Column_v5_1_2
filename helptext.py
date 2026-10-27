"""Help texts shown by the (?) icons of the v5 app – one place, plain English, CEDA rules quoted with their source."""

H = {
    # ------------------------------------------------------------------ steps
    'step_files': 'Upload the same file set as the BKMPH02 project. Files stay in this session until you load another project.',
    'step_inputs': 'Every input the design needs. Prefilled from ETABS, the lap table and the input workbook. What you see here is '
                   'what runs, and "Save inputs to Excel" writes it back to the CEDA input workbook.',
    'step_check': 'Checks that every column-story has forces, a section, Lu and defined combos before the design can run.',
    'step_fc': "Project-level f'c decision (one bottom f'c, one reduction to the typical f'c). Compare the what-if scenarios with "
               "their quantities and cost, then choose one. f'c is never changed per column.",
    'step_fix': 'Every column-story that does not pass, needs ρ above 6 % or has δ above 1.4. Choose an action per row, preview it '
                'in seconds, then apply all actions and re-run once.',
    'step_results': 'Label → mark, Table of Column, quantities, interaction surface and the column plan of the latest run.',
    'step_docs': 'Calculation PDF, back-up Excel, Table of Column DXF/PDF and schedule. Made on request because they take minutes.',
    # ------------------------------------------------------------------ files
    'f_seismic': 'ETABS export of the seismic model (above ground, reduced stiffness): Element Forces – Columns with the EQ combos, '
                 'Column / Point Object Connectivity, Frame Assignments – Section Properties, section definitions, and Story '
                 'Forces / Story Drifts if available (sway check). Several workbooks are merged.',
    'f_full_unreduced': 'ETABS export of the full model used for gravity (BKMPH02: "02 Full Gravity"). Include DL/SDL/LL load cases for '
                        'every story (βd and basement ΔP). When no reduced-stiffness full model is given, this one is used for '
                        'geometry, βd and the basement ΔP – reported as an ASSUMPTION.',
    'f_full_reduced': 'Optional. Full model with reduced (cracked) stiffness. When given it is the primary full model (design basis '
                      'Rev.1) and the gravity combos are enveloped with the unreduced model.',
    'f_combos': 'ETABS table "Load Combination Definitions" (with or without its TABLE: row). Used in every model; a combo with the '
                'same name replaces the ETABS definition. Combos are never judged by their name (กฎกระทรวง ข้อ 7 check).',
    'f_lap': 'CEDA development-length workbook (TABLE 11.04). Lst = Class B tension lap, other bar, per f\'c and bar size. Used when '
             'the input workbook has no Lap rows. Pick the sheet of the project cover (e.g. 40mm).',
    'f_workbook': 'CEDA column input workbook. Loading it replaces the inputs on screen with the workbook content.',
    'f_project': 'A project file saved from this app (.zip): uploaded files, inputs on screen and the chosen f\'c scenario. '
                 'Overload acceptances are not saved – they are asked again in every session (CEDA rule).',
    'f_lapsheet': 'Sheet of the development-length workbook to read; one sheet per concrete cover.',
    # ------------------------------------------------------------------ criteria
    'project.name': 'Project name for the calculation header.', 'project.location': 'Location for the header.',
    'project.building': 'Building name for the header.', 'project.job': 'Job number. Also the prefix of every output file.',
    'project.date': 'Date shown on the calculation sheets.', 'project.calc_by_1': 'Calculated by: name, licence number.',
    'project.calc_by_2': 'Checked by: name, licence number.', 'project.approve_by': 'Approved by: name, licence number.',
    'seismic.design': 'Seismic design required (มยผ. 1301/1302-61).',
    'seismic.category': 'Seismic design category ก/ข/ค/ง (มยผ. 1301/1302-61). Category ง with ordinary walls: height ≤ 60 m and '
                        'seismic force +40 %.',
    'seismic.frame': 'Ductility of the columns: gravity (not part of the lateral system), IMF or SMF. Hoops are at least IMF in every '
                     'case (ประกาศ มท. 2564 ข้อ 26(1)); SMF detailing (ACI 18.7) is not automated.',
    'seismic.zone': 'Seismic zone (header only).', 'seismic.importance': 'Importance factor I (header only).',
    'seismic.system': 'Lateral system name (มยผ. 1301/1302-61 Table 2.3-1).', 'seismic.R': 'Response modification factor R.',
    'seismic.Omega0': 'Overstrength factor Ω0.', 'seismic.Cd': 'Deflection amplification factor Cd.',
    'materials.fc_typical': "Typical (general) f'c of the project, cylinder. Columns reduce to it once (CEDA).",
    'materials.fy': 'Yield strength of longitudinal bars (SD50 = 5,000 ksc for every bar size at CEDA).',
    'materials.fyt': 'Yield strength of ties. DB12 SD40 = 4,000 ksc; DB16–32 are limited to 4,200 ksc for shear.',
    'materials.fc_slab': "Slab f'c. ACI 15.5: a joint check is flagged where column f'c > 1.4 × slab f'c.",
    'materials.fc_mode': "auto = the f'c study chooses (recommended scenario, see step 4). fixed = the f'c per story of the Stories table, "
                         "or the bottom f'c below the reduction story.",
    'materials.fc_bottom': "Fixed mode: f'c below the reduction story (used when the Stories table has no f'c).",
    'materials.fc_reduce_at': "Fixed mode: first story with the typical f'c.",
    'detailing.cover_mm': 'Clear cover to the ties, mm (CEDA columns: 40 mm).',
    'detailing.tie_db': 'Tie bar size, mm.',
    'detailing.size_restricted': 'Column size restricted by architecture. Only then may ρ between 6 % and 8 % be approved (never above 8 %).',
    'slender.k': 'Effective length factor k (default 1.0, non-sway). Lu / k per story or per column override it.',
    'slender.beta_d': 'βd for the moment magnifier. Blank = from the DL/SDL/LL load cases per column (25 % of LL sustained).',
    'slender.sway': 'Blank = sway check Q from Story Forces + Story Drifts (ACI 6.6.4.3). non-sway = assumed by the engineer when those '
                    'tables are not exported (Engineering judgment, reported).',
    'gravity.DL': 'ETABS load case names counted as dead load (comma separated).',
    'gravity.SDL': 'ETABS load case names counted as superimposed dead load.', 'gravity.LL': 'ETABS load case names counted as live load.',
    'marks.envelope': 'Mark envelope (criterion A): a label may join a heavier mark of the same section.',
    'marks.max_weight_pct': 'Criterion A: extra longitudinal steel allowed per label when it joins a heavier mark (CEDA: 25 %).',
    'marks.project_max_weight_pct': 'Criterion A: extra longitudinal steel allowed for the whole project (CEDA: 10 %).',
    'marks.max_rows': 'Optional limit of rows that may differ inside a mark. Blank = no limit (criterion A).',
    'marks.max_step': 'Optional limit of ladder steps per row. Blank = no limit.',
    'story_ranges.mode': 'auto = basement every story, above ground 2–3 stories per range (12 m bar + Lst). each = every story a row. '
                         'A Story ranges table below overrides both.',
    'fc.outlier_pct': "f'c study: failing columns allowed per story before the bottom f'c is raised or the reduction moves up (S10). "
                      "CEDA 23 Oct 2026: 10 %.",
    'fc.outlier_max_pct': "f'c study: if keeping D/C ≥ 0.75 needs a lower f'c, failing columns may go up to this share per story (S25). "
                          "CEDA: 25 %.",
    'fc.dc_min': "f'c study: a passing column below this D/C is under-used (concrete stronger than needed). Not counted when the "
                 "column already has the typical f'c and minimum steel.",
    'fc.exempt_rho_pct': "Minimum steel that exempts a column at the typical f'c from the D/C floor (CEDA: 1–1.5 %).",
    'fc.share_low_pct': "Reduction story: share of its columns that need ρ ≤ 1.5 % with the typical f'c (CEDA: 50–60 %).",
    # ------------------------------------------------------------------ tables
    't_stories': 'Bottom → top. z only when ETABS has no Point Object Connectivity. Lu_m / k apply to the whole story. basement = Y '
                 'for stories below the seismic model. fc_ksc = fixed f\'c of the story (fixed mode).',
    't_columns': 'One row per column-story: Lu / k of that column only (e.g. ramp columns with deep beams: Lu = clear height). '
                 'XY only to match labels between models.',
    't_sections': 'Section set by the designer for the label-stories listed (blank stories = all). b = t2 (bends about My), '
                  'h = t3 (bends about Mx), mm. The forces stay those of the current ETABS model – update ETABS and re-run.',
    't_combos': 'Factors per ETABS load case for combos that have no definition, or to replace one (row wins).',
    't_lap': 'Class B tension lap Lst (other bar), mm, per f\'c and bar size. Blank = unknown – never invented.',
    't_ranges': 'Story ranges fixed by the designer, bottom → top, every story exactly once (e.g. +00 → GF merged).',
    't_prices': "Material unit prices for the f'c what-if cost: concrete THB/m³ per f'c, longitudinal steel THB/kg per bar size. "
                "Formwork and labour are not included. Blank = quantities only.",
    't_approve': 'Label-stories approved for 6 % < ρ ≤ 8 % (needs "Column size restricted").',
    't_delta': 'Label-stories whose moment magnifier above 1.4 is accepted up to delta_max (ACI 6.2.5.3 limit 1.4 – Engineering judgment).',
    't_overload': 'Proposed overload acceptances (label, story, D/C limit). NOT applied until each row is confirmed in the fix board of '
                  'this session – CEDA rule: overload is never accepted without asking, every run.',
    'cases': 'ETABS load case names used as the columns of the combo table (comma separated).',
    'exclude': 'Combos left out of the design (e.g. cross-standard U_B combos, or a duplicate gravity combo).',
    # ------------------------------------------------------------------ check / run
    'check': 'Each input with its source. ✖ items must be fixed in step 2 (or in the workbook) before the run.',
    'confirm': 'The design never runs before the criteria are confirmed (skill rule).',
    'run': 'Runs the design engine (run.py): load assembly, f\'c, bars, ranges, marks. Documents are made later in step 7.',
    'route': 'Which uploaded model is used for what. ASSUMPTION lines must be accepted by the engineer.',
    # ------------------------------------------------------------------ f'c study
    'fc_table': "One row per project scenario: bottom f'c below the reduction story, typical f'c above. Failing = no arrangement passes "
                "with ρ ≤ 6 % (8 % approved). Under-used = D/C below the floor. Quantities: concrete per f'c, longitudinal steel per bar "
                "size of the lowest passing arrangement per column-story, before story ranges and marks; ties, laps and couplers "
                "excluded. Cost = quantities × the Prices table.",
    'fc_choose': "Uses the scenario for the whole project (f'c mode fixed) and re-runs the design. The choice is written to the "
                 "decisions log.",
    'fc_run': "Runs the f'c study on the current run (needed when f'c mode is fixed). About one minute on BKMPH02.",
    'fc_tags': 'S0 = no failing column (rule before v1.4). S10 = failing ≤ 10 % per story. S25 = failing ≤ 25 % per story with the '
               'fewest under-used columns. RECOMMENDED = S25 when it has fewer under-used columns than S10, else S10.',
    # ------------------------------------------------------------------ fix board
    'fix_table': 'Pick an action per row, set its value, press Preview to re-check those rows in seconds, then Apply all and re-run. '
                 'Preview checks one column-story only; story ranges, the never-less-than-above rule and marks are redone by the run.',
    'fix_action': 'Enlarge section (b, h) · Approve ρ ≤ 8 % (sets "Column size restricted") · Accept overload up to D/C limit · '
                  'Accept δ up to the limit. f\'c is changed for the whole project in step 4, never per column.',
    'fix_batch': 'Apply the same action and values to several rows at once.',
    'fix_preview': 'Re-checks the rows that have an action (same bar order as the design, current ETABS forces).',
    'fix_apply': 'Writes the actions into the inputs (Sections, Approve_rho, Accept_delta, confirmed overload) and re-runs the design.',
    'fix_confirm': 'Required for rows with "Accept overload": Engineering judgment – ACI 318 requires φSn ≥ U. Logged with name and time.',
    'dc_engine': 'D/C of the arrangement the engine ended with. For REVISE it is the lowest D/C reached with the most steel that fits.',
    # ------------------------------------------------------------------ results / docs
    'm_marks': 'Number of column marks after criterion A envelopes.', 'm_ranges': 'Rows of the Table of Column.',
    'm_ok': 'Column-stories with D/C ≤ 1 and ρ ≤ 6 % (or approved).', 'm_acc': 'Column-stories whose overload the engineer accepted.',
    'm_ask': 'Column-stories that need 6 % < ρ ≤ 8 % – approve in the fix board or change the section.',
    'm_rev': 'Column-stories that do not pass – see the fix board.',
    'boq': 'Quantities of the final design (after ranges and marks): concrete per f\'c and longitudinal steel per bar size.',
    'docs_make': 'Makes every document of the current run. Takes several minutes on a large project.',
    'plan': 'Column mapping plan of one story: true-size sections, mark and label. Local axis angle 0 assumed.',
    'save_inputs': 'Download the inputs on screen as a CEDA input workbook (Excel).',
    'save_project': 'Download the whole project (files + inputs) to continue later with "Open project".',
}


H.update({
    # ------------------------------------------------------------------ v5 steps
    'step_check': 'Checks that every column-story has forces, a section, Lu and defined combos. The run designs every column at '
                  "ρ ≤ 6 % and builds the f'c case table (workbook approvals are not used before the fix board).",
    'step_fc': "One f'c for the whole project, by story. Each candidate f'c of the development table gives case A (lowest reduction "
               "story with failing within the limit) and case B (lowest reduction story with no failing column above it). Pick "
               "one case; f'c is never changed per column.",
    'step_fix': 'One row per label and kind. Choose the action of every row, preview it, then apply all actions with one re-run. '
                'Enlargement is evaluated first; approvals are re-checked on the new section.',
    'step_final': 'Everything after the fix board ends here: check with the old forces, update ETABS, upload the new forces, '
                  "compare, fix again on this page and finish. The f'c case and the mark names stay locked.",
    'step_results': 'Table of Column, column detail (interaction surface + section), quantities and the column plan of the latest run.',
    # ------------------------------------------------------------------ v5 criteria
    'detailing.rho_max_pct': 'CEDA practice: every column is designed and studied with ρ ≤ 6 % (steps 3–4). Above it only by '
                             'approval on the fix board.',
    'detailing.rho_ask_pct': 'Highest ρ the fix board may approve. Adjustable 6–8 % (ACI 318-19 §10.6.1.1: ρ ≤ 8 %). SMF: locked at 6 % '
                             '(ACI 318-19 §18.7.4.1).',
    'detailing.splice': 'Project default splice. Lap – staggered: laps of the bars of a bundle do not overlap, Lst ×1.2 (3-bar) / '
                        '×1.33 (4-bar) (ACI 318-19 §25.6.1.5, §25.6.1.7). Lap – one level: not allowed with 3–4-bar bundles. '
                        'Mechanical coupler: ≥ 1.25 fy (§25.5.7), no lap length. Clauses to be confirmed by the engineer.',
    'fix.target_dc': 'ASSUMPTION (10 % margin): an enlarged section attracts more force, so proposals and typed sizes must reach '
                     'D/C ≤ this value with the forces of the current ETABS export. Round 2 (new forces) uses D/C ≤ 1.00.',
    'fix.step_mm': 'Sizes grow in this step (CEDA 50 mm).', 'fix.max_add_mm': 'ASSUMPTION – upper bound of the search per side.',
    'fix.compare_ddc': 'ASSUMPTION – the round compare lists by default the label-stories whose D/C changed more than this.',
    'marks.renumber': 'At Mark FINAL: rename the marks by section size (C1 = largest). Names only – the groups do not change.',
    'fc.limits_pct': "Case A: the lowest reduction story where every story has failing ≤ max(limit × columns of the story, 1). One "
                     "recommended case per limit (lowest f'c first, then the lowest story).",
    'fc.max': "Highest f'c tried. Only values of the development table are used (common in Thailand); above 700 ksc is rarely used.",
    'fc.dc_min': 'Information only: D/C below this is counted as low D/C; never rejects a case.',
    'fc.dc_low': 'Information only: the lower band of the low-D/C columns.',
    'fc.exempt_rho_pct': "Typical-f'c column-stories with ρ ≤ this are not checked for low D/C (their size is set by other reasons).",
    'fc.share_low_pct': "A story may be the reduction story only when at least this share of its columns needs ρ ≤ 1.5 % at the "
                        "typical f'c.",
    # ------------------------------------------------------------------ v5 f'c table
    'fc_fail': 'Label-stories with D/C > 1 at ρ ≤ 6 % in this case. ρ 6–8 % = pass with ρ up to the approval limit; Enlarge = fail '
               "even then; Never = fail at the highest f'c even with the approval limit.",
    'fc_above': "Failing in the typical-f'c stories – fixed only by moving the reduction story up (case B) or by enlargement.",
    'fc_share': 'Worst story: failing ÷ columns of that story.',
    'fc_fcov': "High-f'c column-stories with D/C < 0.75 that would still pass with D/C ≥ 0.75 at the typical f'c. % = their "
               "concrete ÷ all high-f'c concrete of the case (concrete at overstrength).",
    'fc_low': "D/C at the f'c of each story; % of the checked label-stories (all except typical f'c with ρ ≤ 1.5 %).",
    'fc_conc': "Column concrete of the whole project by f'c (sections as input).",
    'fc_steel': 'Longitudinal bars of all columns, lowest passing arrangement × story height, before story ranges and mark envelopes; '
                'ties, laps and couplers not included. For comparing cases, not a BOQ.',
    'fc_cost': 'Information only, from the prices on step 2. Not a decision rule.',
    'fc_use': "Sets f'c fixed with this story map, re-runs the design (≈ 40 s) and locks the mark names. Logged with your name.",
    # ------------------------------------------------------------------ v5 fix board
    'fix_engineer': 'Entered once. Every accepted row (overload, ρ approval, δ) is logged with this name, the date and its values.',
    'fix_action': 'Enlarge – proposal: the size chosen in the detail. Enlarge – type size: your own size (D/C ≤ target). '
                  'Approve ρ 6–8 %: only when ρ up to the approval limit passes (D/C ≤ 1.00). Accept overload: D/C limit + tick in '
                  'the row, every time. No action: the row stays open (step 6).',
    'fix_range': 'Option 1 = only the Table-of-Column row of the failing story. Option 2 = from the failing story down to the lowest '
                 'story; lower stories are re-designed on the new size and may carry less steel than the failing story (logged).',
    'fix_props': 'Proposals in 50 mm steps up to +500 mm per side, D/C ≤ target with the current ETABS forces: within the larger '
                 'section below first (common side kept), then short side / long side / keep b/h ratio; circular: diameter.',
    'fix_overload': 'CEDA rule: overload (D/C > 1) is never accepted silently. Tick every row yourself; the tick is not saved in the '
                    'project file.',
    'fix_splice': 'Project default from step 2. Override here only where needed (e.g. a mechanical coupler).',
    'fix_delta': 'ACI 318 moment magnifier limit 1.4 (CEDA practice). Accept up to a limit with a reason, or enlarge.',
    'fix_wb': 'Approve_rho rows of the input workbook: pre-selected, checked against this case, applied only with Apply.',
    'fix_preview': 'Quick check of every row with its action, in seconds. Nothing is changed.',
    'fix_apply': "Writes the actions to the inputs and re-runs the design once with the locked f'c case and mark names.",
    # ------------------------------------------------------------------ v5 final check
    'fin_rounds': 'One row per ETABS export. Round 1 uses the forces of the export with the old sizes (PROVISIONAL).',
    'fin_etabs': 'Excel list of the new sizes, one row per label and story range, to update the frame sections in every ETABS model.',
    'fin_upload': "Upload only the new model exports. Combinations, lap table, inputs and decisions are kept. The re-check uses the "
                  "locked f'c case – the f'c study is not run again.",
    'fin_match': 'The size of every enlarged label in the new export must equal the design size.',
    'fin_compare': 'Every label-story is compared; shown by default: enlarged, |ΔD/C| above the threshold, failing.',
    'fin_finish': 'FINAL needs forces from an ETABS export that already has every final size and 0 open issues; otherwise continue '
                  'as PROVISIONAL with your name.',
    'detail': 'Pick a label and story: the interaction surface and the section drawn to scale (bars, bundles, hoops) of that column-story.',
})


def h(key):
    return H.get(key, '')
