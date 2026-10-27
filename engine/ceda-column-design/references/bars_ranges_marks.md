# Bars, ties, story ranges and marks (engine: layout.py, design.py, run.py)

## 1 Bar positions – one grid per column (layout.Grid, face_count)
| face dimension | bars on the face (incl. corners) | tag |
|---|---|---|
| ≤ 200 mm | 2 | Practice (CEDA 19 Oct 2026) |
| > 200 – 540 mm | 3 | Practice |
| > 540 – 660 mm | 4 | Practice |
| > 660 mm | count giving c/c 125–150 mm (fewest bars); none fits → closest count with clear ≤ 150 mm (ACI 25.7.2.3) and ≥ code minimum (ACI 25.2.3), note | Practice / Code |

Clear spacing ≥ max(1.5 db,eq, 40 mm, 4/3 dagg) with db,eq = db√n for bundles (ACI 25.2.3, 25.6.1.6); dagg 25 mm (Assumption, stated).
A single size that breaks it on the grid is removed from the ladder (note). Bundle width along the face: db (2 bars), 2 db (3–4 bars).
Circular: n = ceil(π·Dcore / 150 mm), ≥ 6.

**Wider grid for 3–4-bar bundles – Practice (CEDA 20 Oct 2026).** Singles and 2-bar bundles always use c/c 125–150. When no step on that
grid passes in a story range, the range is re-designed on a second grid with c/c up to 160 mm (`detailing.cc_bundle34`, default
[125, 160]) whose ladder keeps only arrangements with 3–4-bar bundles; it is used only if the status improves (REVISE → ASK_RHO / OK).
Required c/c for DB32 (bundle width 2 db, clear ≥ 1.5 db√n): 3 beside 3 → 83 + 64 = 147 mm; 4 beside 4 or 3 → 96 + 64 = 160 mm;
4 beside ≤ 2 bars → 96 + 48 = 144 mm. Example 900 mm face: 7 bars c/c 127.3 (max 48-DB32 in 2-bar bundles, ρ 4.77 %) → 6 bars c/c 152.8
(up to 56-DB32 with 4-bar bundles at the corners, ρ 5.56 %). A lower range with the same section and f'c moves to the wider grid when it
would otherwise carry less steel; the grid change is a splice point (note). 4-bar bundles: Lst × 1.33 or couplers (ACI 25.6.1.5).

**Inner bars at the tie crossings – Practice (CEDA pattern paattern.dxf, 20 Oct 2026).** Perimeter full, still not enough →
one bar (same size) at every crossing of the legs of the inner hoops (vertical hoops × horizontal hoops), e.g. 1100×900: 8 bars at
x 205.7 / 481.1 / 618.9 / 894.3, y 322.7 / 577.3 mm; 900×900: 4 bars at 322.7 / 577.3 mm. Order: 125–150 grid → wider grid
(3–4-bar bundles) → inner bars on the 125–150 grid → inner bars on the wider grid. Allowed only (1) in basement stories, where the
column is compression-dominated (governing e/h is reported for confirmation), or (2) for label-stories approved for ρ > 6 % whose
perimeter cannot take more bars. Never on circular columns. Inner bars sit near the centroid: full help for axial load, little for
moment. The same drawing confirms the 2-bar bundle shape: second bar stacked inward (width along the face = db), diagonal at corners.

## 2 Smallest bar and 1 % pattern (design.min_bar_size, pattern_step)
Smallest bar by the **long side**: ≤ 200 mm DB12, > 200 mm DB16, > 500 mm DB20. 1 % pattern = first single size on the grid with
As ≥ 1 % Ag (ACI 10.6.1.1); never more bars than the grid – e.g. C1 2000×450: 30 positions → 30-DB20 = 94.2 cm² ≥ 90 cm².

## 3 Build-up ladder (layout.ladder)
1. Singles of increasing size up to DB32 on the same grid.
2. Bundles of DB32 – **Practice, CEDA 20 Oct 2026**: bundles are allowed at any position, but each bundle size is completed over the
   whole section before the next: 2-bar bundles at the tie corners (column corners first, then hoop corners outside → inside), then
   2-bar bundles at the other positions (symmetric, outside → inside), then 3-bar bundles in the same order, then 4-bar (ACI 25.6.1.1);
   a step breaking clear spacing is skipped. Phase 1 = only tie corners carry bundles, phase 2 = other positions too (no longer an assumption).
3. 3–4-bar bundles: splice with couplers (CEDA); a lap would need ×1.2 / ×1.33 (ACI 25.6.1.5).
Lowest passing step per column-story (D/C ≤ 1, ρ ≤ 6 %; 6–8 % → ASK_RHO; nothing passes → REVISE).

## 4 Ties (layout.ties, _support_pattern, _pairs)
Every corner and alternate bar supported, no unsupported bar > 150 mm clear from a supported one (ACI 25.7.2.3) – **Code**.
CEDA symmetric pattern – **Practice**: even count → centre pair in one hoop, then every second bar to the corners; odd count → every
second bar from the corners; a gap of two unsupported bars next to a corner is filled. Supported intermediate bars are paired into closed
hoops outside-in (4+ left: outer two at each end; 3 left: hoop over the outer two + crosstie; 1 left: crosstie).
Example C1 2000 face (14 positions): supported 0, 2, 4, 6, 7, 9, 11, 13 → hoops (2,4), (6,7), (9,11) + outer = 4 sets.

## 5 Going up the column (run.py)
Remove bundles first, then reduce the size, down to the 1 % pattern. A story never carries less than the story above with the **same
section and the same f'c**; at the f'c reduction the lower (stronger) story may carry less – bars change there (note) – **Practice**.
Section change along the height → the rule restarts on the new grid, note for bar continuity – **Practice**.
v1.5.0 exception: inside an option-2 enlarged range (fix board) the stories below are re-designed with the normal rules and the
never-less-than-above rule is relaxed between enlarged stories (logged); the extra bars of the upper story run Lst below its floor –
**Engineering judgment (CEDA 27 Oct 2026)**. No carry-down from a REVISE story.

## 6 Common story ranges = rows of the Table of Column (design.story_ranges)
One set of ranges for the whole project, bottom → top – **Practice**:
- basement: a break at every story;
- above ground: 2–3 stories so that Σh + Lst ≤ 12 m (Lst = largest lap of the project table), closed earlier when any label can remove
  its bundles or halve its steel at the next story – guidance, not a fixed limit;
- a change of f'c is always a break; `mode = each` or fixed `groups` from the designer.
Each label takes the governing step of each range; every range stays a row, no row limit; consecutive equal rows are drawn as merged cells.

## 7 Marks (run.py)
1. Same label (plan position) = same mark in every story.
2. Same mark when the section is the same in every row (**90° rotation = same section**, orientation on plan), same story span,
   same bars **and ties** (so, s, added crossties).
3. Envelope (default on) – **criterion A, CEDA 20 Oct 2026** (replaces ≤ 2 rows / ≤ 1 step / ≤ 20 % of 19 Oct): a label joins a
   heavier mark (labels taken heaviest first) when, for every member, the row-wise maximum ladder step adds ≤ 25 % longitudinal steel
   (Σ As × range height) to its own design, the envelope never lifts a non-approved label-story above ρ 6 %, and the steel added by all
   envelopes stays ≤ 10 % of the project's longitudinal steel. Row / step limits are off (`mark_envelope.max_rows / max_step`, blank).
   BKMPH02: 43 → 29 marks for +4.8 % steel. Trial curve (same project): per-label 10 % → 34 marks (+1.5 %), 20 % → 29 (+4.2 %),
   30 % → 24 (+9.5 %).
   Ties of a mark = critical member per row. Members are re-checked with the mark's bars and ties; every envelope is noted.
4. Names C1, C2 … by section area, largest first; heaviest member = reference label (drawing orientation).
5. v1.5.0: names are locked after the f'c case (sheet Marks); a new group gets the next free number; renumber by size only at FINAL
   (names only – a Mark rename table is issued with the documents).
