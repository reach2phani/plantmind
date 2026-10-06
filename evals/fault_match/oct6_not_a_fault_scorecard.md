# Fault match check — oct6_not_a_fault

Run 2026-10-06 09:16. Matcher: **meaning**. Right = exactly the expected fault and sure. Unsure = expected fault among the close candidates, flagged. Wrong = anything else.

| Machine | Set | Right | Unsure | Wrong | False CRITICAL |
|---|---|---|---|---|---|
| FL-101 | fresh_oct | 5/5 | 0/5 | 0/5 | 0 |
| **All** | | **5/5** | 0/5 | 0/5 | 0 |

## Every question

| Id | Expected | Got | Confidence | How | Top scores |
|---|---|---|---|---|---|
| FR-01 | none |— | none | AI: not one of these faults | Overfill 0.791; Underfill 0.786; Infeed Jam 0.785 |
| FR-02 | Underfill |Underfill | sure | AI tie-break | Underfill 0.857; Overfill 0.844; Product Supply Pressure Low 0.816 |
| FR-03 | Underfill |Underfill | sure | meaning | Underfill 0.832; Overfill 0.795; Infeed Jam 0.794 |
| FR-04 | Infeed Jam or none |— | none | AI: not one of these faults | Underfill 0.797; Infeed Jam 0.79; Product Supply Pressure Low 0.785 |
| FR-05 | none |— | none | AI: not one of these faults | Underfill 0.792; Overfill 0.787; Infeed Jam 0.772 |