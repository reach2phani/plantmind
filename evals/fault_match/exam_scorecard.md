# Fault match check — exam

Run 2026-09-30 07:46. Matcher: **meaning**. Right = exactly the expected fault and sure. Unsure = expected fault among the close candidates, flagged. Wrong = anything else.

| Machine | Set | Right | Unsure | Wrong | False CRITICAL |
|---|---|---|---|---|---|
| FL-101 | fresh | 7/7 | 0/7 | 0/7 | 0 |
| **All** | | **7/7** | 0/7 | 0/7 | 0 |

## Every question

| Id | Expected | Got | Confidence | How | Top scores |
|---|---|---|---|---|---|
| FL-f1 | Underfill | Underfill | sure | meaning | Underfill 0.867; Overfill 0.829; Product Supply Pressure Low 0.821 |
| FL-f2 | Overfill | Overfill | sure | AI tie-break | Overfill 0.828; Underfill 0.813; Infeed Jam 0.791 |
| FL-f3 | Infeed Jam | Infeed Jam | sure | meaning | Infeed Jam 0.865; Overfill 0.822; Underfill 0.82 |
| FL-f4 | Glass Breakage | Glass Breakage | sure | meaning | Glass Breakage 0.846; Infeed Jam 0.804; Overfill 0.799 |
| FL-f5 | Product Supply Pressure Low | Product Supply Pressure Low | sure | meaning | Product Supply Pressure Low 0.895; Underfill 0.835; Overfill 0.828 |
| FL-f6 | Underfill | Underfill | sure | AI tie-break | Overfill 0.824; Underfill 0.819; Product Supply Pressure Low 0.812 |
| FL-f7 | Infeed Jam | Infeed Jam | sure | AI tie-break | Infeed Jam 0.808; Overfill 0.802; Underfill 0.788 |