# Method – strength, slenderness, shear, ties, f'c, lap (engine: design.py, colsurf.py)

Units in the engine: kg, cm, ksc; moments kg-m. Reports: t, t-m, ksc. Tags: **Code** / **Practice** / **Judgment** / **Assumption**.
Basis document: `Column_Design_Basis_Rev1.pdf` (11 Oct 2026); Excel review: `Column_Excel_Review_Rev0.pdf`.

## 1 Section strength (colsurf.py)
- Strain compatibility, εcu = 0.003, Es = 2.04×10⁶ ksc, Ec = 15,100√f'c (ACI 19.2.2.1, ksc form) – **Code**.
- Concrete: ACI rectangular block on a fibre grid (≥ 30 fibres per side), β1 = 0.85 − 0.05(f'c − 280)/70, 0.65 ≤ β1 ≤ 0.85 (ACI 22.2.2.4.3) – **Code**.
- Steel: elastic–perfectly plastic ±fy; bars at their true positions incl. bundle offsets (layout.bars_cm) – **Code / Practice**.
- Po = 0.85 f'c (Ag − Ast) + fy Ast (ACI 22.4.2.2); φPn,max = 0.80 φ Po tied, 0.85 φ Po spiral (ACI 22.4.2.1) – **Code**.
- φ (กฎกระทรวงกำหนดการออกแบบโครงสร้างอาคาร … พ.ศ. 2566 ข้อ 8 วรรคสอง, quality-controlled column): tied 0.70, spiral 0.75,
  flexure / tension 0.90, shear 0.85, bearing 0.70 – **Code**.
- φ transition: φ = φc + (0.90 − φc)(εt − εty)/0.003 between εty and εty + 0.003 (ACI 318-19 21.2.2; not in กฎกระทรวง) – **Code (ACI)**.

## 2 Biaxial check (colsurf.Section.surface / dc)
- Points (φPn, φMnx, φMny) for neutral-axis angle θ (72 values) × depth c (60 values, geometric + linear), axial capped at φPn,max,
  pure tension −φt fy Ast; convex hull of the points scaled by (φPn,max, φPn,max·h/4, φPn,max·b/4) – **Judgment** (agreed).
- D/C = radial distance origin → demand / origin → hull along the same ray; on the capped part D/C = max(uncapped, Pu/φPn,max).
  No Bresler – **Judgment**.

## 3 Slenderness – non-sway (design.magnified)
- Sway test: Q = ΣPu Δo / (Vus lc) per story and direction; Q > 0.05 → STOP (δs not automated) (ACI 6.6.4.3) – **Code**.
- r = 0.3 h (rect), 0.25 D (circle) (ACI 6.2.5.2); limit kLu/r ≤ 22 with M1/M2 = +1 – **Code / Practice**.
- (EI)eff = (0.2 Ec Ig + Es Ise)/(1 + βd), Ise from the true bar positions (ACI 6.6.4.4.4(a)) – **Code**.
- Pc = π²(EI)eff/(k Lu)², **without φ** (designer decision D3) – **Judgment**.
- δ = Cm / (1 − Pu / 0.75 Pc) ≥ 1, **Cm = 1 always** – **Practice**; δ > 1.4 reported (ACI 6.2.5.3).
- Mu = sign(M)·max(|M|, M2,min)·δ, M2,min = Pu (15 + 0.03 h) mm = Pu (1.5 + 0.03 h) cm, applied only when slender (ACI 6.6.4.5.4) – **Code**.
- βd = [1.4(DL + SDL) + 0.25·1.7 LL] / [1.4(DL + SDL) + 1.7 LL] per column-story from the load cases at the column bottom
  (25 % of LL sustained, conservative) – **Judgment (Rev.1)**; a single value from Criteria when the cases are not exported.
- Defaults: k = 1.0, Lu = column length from connectivity (conservative); per story / per column overrides – **Judgment**.

## 4 Shear (design.shear_check, design_shear)
- Each direction separately; Vc = 0.53 √f'c bw d, **no axial-compression increase**; tension: Vc × max(1 + Nu/(35 Ag), 0) – **Practice / Code**.
- Vs = Av fyt d / s ≤ 2.1 √f'c bw d; only legs running the full depth count; Av,min = max(0.2√f'c, 3.5) bw s / fyt when Vu > 0.5 φ Vc – **Code**.
- fyt for shear: DB12 4,000 ksc; DB16–DB32 ≤ 4,200 ksc (Ash uses the actual fyt) – **Practice**.
- IMF: Ve = lesser of 2 Mn/Lu (max Mn over the Pu range) and 2 × seismic-combo shear (มยผ. 5.2.7.2 / ACI 18.4.3.1, upper bound) – **Code / Judgment**.
- When shear fails: s → 150 mm, then full-depth crossties, then s 100 mm, otherwise DB16 ties / revise – **Practice**.

## 5 Minimum ties – IMF level for every column (design.imf_ties)
ประกาศกระทรวงมหาดไทย 2564 ข้อ 26(1) = มยผ. 1301/1302-61 5.2.7.4 – **Code**:
so ≤ min(8 db,min, 24 dt, c/2, 300 mm); lo ≥ max(Lu/6, c1, 500 mm); first tie ≤ so/2; outside lo s ≤ 2 so.
Joint Av ≥ 3.5 c1 s / fy (มยผ. 5.2.7.4.4) – not automated, remind. SMF (ACI 18.7) – not automated.

## 6 f'c study (fc_study.py)
**v1.5.1 (CEDA 28 Oct 2026):** row **T** first = typical f'c in every story – always shown, also when its failing exceed every limit (comparison); recommended at every limit it satisfies.

**v1.5.0 (CEDA 27 Oct 2026) – cases.** Every column is designed at its input size (no size_restricted list); ρ ≤ 6 % in the study.
For each development-table f'c above the typical one (up to `fc.max`, 700): case A = lowest valid reduction story, case B = highest;
failing allowed per story = max(L × n, 1) for every limit L of `fc.limits_pct` (10, 15, 20, 25 %); the loop stops when case B has no
failing column or f'c = 700; A = B shown once. Recommended per limit: lowest f'c, then lowest story. Columns per case: failing
(fixable by ρ 6–8 % / enlarge / never), failing above the reduction story, max share per story, f'c-overstrength = high-f'c segments
that would pass with the typical f'c (n · % of high-f'c concrete volume), low D/C % (< `fc.dc_low` 0.50 and 0.50–0.75, each story at
its own f'c, over every segment except typical f'c with ρ ≤ `fc.exempt_rho_pct` 1.5 %), concrete m³ high / typical, main bars t
(longitudinal only, before ranges and envelopes), cost (information only). BKMPH02 600/3F: 9 failing (4 ρ, 5 enlarge),
overstrength 252 · 39 %, low D/C 22 % / 37 % of 867.

**v1.4.0 rule (kept for reference)**
Standard f'c 210, 240, 280, 320, 400, 450, 500, 560, 600, 700 ksc (S-00-04-04). f'c is a **project** decision: one bottom f'c below one
reduction story, the typical f'c above – never per column – **Practice (designer)**.
1. For every column-story and every f'c ≥ typical: the lowest arrangement that passes with ρ ≤ 6 % (≤ 8 % approved), in the design
   order 125–150 grid → wider grid (3–4-bar bundles) → inner bars (basement / approved only). No pass = FAILING.
2. Column-stories failing with every f'c are listed (enlarge the section) and not counted.
3. Reduction story: ≥ 50 % of its columns at ρ ≤ 1.5 % with the typical f'c (`fc.share_low_pct`).
4. S0 = no failing column (rule before v1.4); **S10** = lowest bottom f'c, then lowest reduction story, with failing ≤ 10 % of every
   story (`fc.outlier_pct`); **D/C floor**: a passing column with D/C < 0.75 is under-used (`fc.dc_min`), except a column at the
   typical f'c with minimum steel (ρ ≤ 1.5 % or its 1 % pattern); **S25** = failing ≤ 25 % of every story (`fc.outlier_max_pct`)
   with the fewest under-used columns. Recommended = S25 when it has fewer under-used columns than S10, else S10.
5. What-if table: every scenario within the 25 % limit with failing / under-used counts, concrete m³ per f'c, longitudinal steel kg
   per bar size (lowest passing arrangement per column-story, before ranges and mark envelopes; ties, laps and couplers not included)
   and cost from the Prices sheet (concrete THB/m³ per f'c, steel THB/kg per bar size, material only). The designer picks the
   scenario; failing columns go to the fix board (enlarge section, approve ρ ≤ 8 %, accept overload – asked every time).
ACI 15.5 check when column f'c > 1.4 × slab f'c – **Code**.

## 7 Lap splices (design.lap_length, run.py)
Lst = Class B tension lap from the project table S-00-04-04 ("other bar") – **Practice**; never invented.
Each project has its own table – VOCO (S-00-04-04): 400 ksc DB25/28/32 = 1550/1875/2325, 560 ksc = 1325/1600/1975
(`S-00-04-04_lap_table.pdf`); BKMPH02 (TABLE 11.04, cover 40 mm, Lst "other bar"): 400 ksc = 1125/1350/1700, 600 ksc = 925/1125/1400.
Never carry a lap table from one project to another.
v1.5.0 splice method (detailing.splice, per label-story sheet Splice): **Lap – staggered** (default; a 3/4-bar bundle lap uses
Lst × 1.2 / × 1.33 – ACI 318-19 §25.6.1.5, **Code**), **Lap – one level** (bundles noted for review), **Mechanical coupler** (no lap
length; coupler type by the designer). Earlier rule (v1.4): 3–4-bar bundles with couplers.

## 8 Status and engineer decisions (design.choose_step, run._status, prepare_inputs)
- OK: D/C ≤ 1 and ρ ≤ 6 %. ASK_RHO: passes only with 6 % < ρ ≤ ρ max with approval (6–8 %, default 7 %; SMF 6 %) – approved on the fix board (v1.5.0). REVISE: nothing fits.
- ACCEPTED: 1 < D/C ≤ dc_max that the designer stated for that label-story (Accept_overload) – **Judgment**, ACI 318 needs φSn ≥ U.
  Asked **every time** (CEDA 21 Oct 2026): rows are applied only with `prepare_inputs.py --overload-confirmed` after the designer
  confirmed them in the session; the lowest steel with D/C ≤ dc_max is used; reported on the calc page ("OVERLOAD ACCEPTED BY THE
  ENGINEER") and in the Summary notes.
- δ > 1.4 (ACI 6.2.5.3): reported; accepted only per label-story by the designer (Accept_delta, **Judgment**).
- Non-sway without Story Forces / Drifts: only when the designer says so (`slender.sway = non-sway`, **Judgment**, reported).
- f'c study: column-stories failing with every standard f'c are excluded from the study and listed (enlarge the section).
- ACI 15.5: column f'c > 1.4 × slab f'c → joint check flagged for the stories concerned (slab f'c asked at start).

## 9 Fix board and final check (fix_tools.py, v1.5.0)
- Size check: the enlarged size is applied to its range (option 1 = the range row; option 2 = failing story down to the lowest story),
  designed to D/C ≤ `fix.target_dc` 0.90 – **Engineering judgment** (10 % margin, CEDA 27 Oct 2026); approvals, δ and round 2 use 1.00.
- Proposals: sizes inside the section below first (common side kept), then short side / long side / ratio (rect) or diameter (circ),
  `fix.step_mm` 50, ≤ `fix.max_add_mm` 500. Option 2 relaxes the never-less-than-above rule inside the enlarged range only (logged);
  bar offsets > 75 mm between faces → dowels instead of cranked bars (ACI 318-19 §10.7.4 – confirm).
- Enlarged forces are from the old ETABS section → PROVISIONAL. Final check: ETABS update list → new exports (same combos, inputs and
  decisions, f'c case locked) → section match → compare old/new (|ΔD/C| > `fix.compare_ddc` 0.05 = **Assumption** to confirm, bars and
  marks changed) → FINAL with 0 open issues; optional mark renumber by size with a rename table.
