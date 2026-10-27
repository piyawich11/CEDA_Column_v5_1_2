# references – method, coefficients, sources

| file | content |
|---|---|
| `method.md` | strength (φ, Po, cap, strain compatibility), biaxial surface, slenderness (EI, Pc, δ, M2,min, βd), shear, IMF ties, f'c study, laps, status and engineer decisions (overload / δ / sway) – with clause tags |
| `bars_ranges_marks.md` | bar grid (125–150, wider grid ≤ 160 for 3–4-bar bundles), small-face table, smallest bar, 1 % pattern, bundle ladder (each size completed before the next), inner bars at tie crossings, tie pattern, going up, story ranges, marks and envelope criterion A |
| `loads_and_inputs.md` | ETABS exports (incl. Point Object Connectivity, sheets without TABLE: row), combo check ข้อ 7, Rev.1 basement load assembly, story naming, CEDA input workbook (Accept_overload / Accept_delta) and merge rule |
| `Column_Design_Basis_Rev1.pdf` | design basis agreed with the designer (11 Oct 2026) – source of most rules |
| `Column_Excel_Review_Rev0.pdf` | review of the CEDA column Excel (Rev6 rectangular / circular) that started the skill |
| `S-00-04-04_lap_table.pdf` | CEDA typical reinforcement details sheet 3 – lap lengths, standard materials |

Codes: กฎกระทรวงกำหนดการออกแบบโครงสร้างอาคาร … พ.ศ. 2566 (ข้อ 7 combos, ข้อ 8 φ); ประกาศกระทรวงมหาดไทย 2564 ข้อ 26;
มยผ. 1301/1302-61 (Table 2.3-1, 5.2.7, 2.11.5); ACI 318-19 (6.2.5, 6.6.4, 10.6.1.1, 15.5, 18.4, 21.2.2, 22.4.2, 22.5, 25.2.3, 25.6.1, 25.7.2.3).
Rules newer than Rev.1 (19–21 Oct 2026: small-face count, f'c-change exception, marks criterion A, wider grid, bundle order, inner
bars (`../tests/fixtures/paattern.dxf`), couplers, overload asked every time, VOCO B6-B5 Lu 2.75 m) are in `bars_ranges_marks.md`,
`method.md` §8 and the SKILL.md change log.
