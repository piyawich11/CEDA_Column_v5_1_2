# BKMPH02 – first real project run (record, not asserted by the self-test)

Engine v1.3.4 (rules of 21 Oct 2026), ETABS exports of BKMPH02 (01 Seismic model, 02 Full Gravity incl. Point Object Connectivity,
04 Load Combination), CEDA lap table 11.04 (Development of Reinforcement Table.xlsx, sheet 40mm).
Result: 92 labels, 1,277 column-stories, 30 marks (+4.1 % steel from the envelope), 1,272 OK + 5 ACCEPTED (overload ≤ 1.10, accepted by
the designer on 21 Oct 2026). Every designer decision with its basis and date: `BKMPH02_Column_Decisions_Log.xlsx`.

Use: after a rule change, rerun BKMPH02 and compare with `bkmph02_results_v1.3.4.csv` row by row; explain every difference in the
SKILL.md change log. The ETABS files are project data and are not stored in the skill.
