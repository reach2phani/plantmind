# Fault match check — oct6_none_fix

Run 2026-10-06 07:59. Matcher: **meaning**. Right = exactly the expected fault and sure. Unsure = expected fault among the close candidates, flagged. Wrong = anything else.

| Machine | Set | Right | Unsure | Wrong | False CRITICAL |
|---|---|---|---|---|---|
| FL-101 | everyday | 6/6 | 0/6 | 0/6 | 0 |
| FL-101 | fresh | 7/7 | 0/7 | 0/7 | 0 |
| FL-101 | fresh_oct | 5/5 | 0/5 | 0/5 | 0 |
| FL-101 | teaching | 3/3 | 0/3 | 0/3 | 0 |
| FL-101 | user | 6/6 | 0/6 | 0/6 | 0 |
| WM-101 | alarm | 6/6 | 0/6 | 0/6 | 0 |
| WM-101 | everyday | 8/8 | 0/8 | 0/8 | 0 |
| **All** | | **41/41** | 0/41 | 0/41 | 0 |

## Every question

| Id | Expected | Got | Confidence | How | Top scores |
|---|---|---|---|---|---|
| FL-01 | Underfill |Underfill | sure | meaning | Underfill 0.895; Overfill 0.863; Product Supply Pressure Low 0.836 |
| FL-02 | Overfill |Overfill | sure | AI tie-break | Overfill 0.86; Underfill 0.837; Product Supply Pressure Low 0.811 |
| FL-03 | Infeed Jam |Infeed Jam | sure | meaning | Infeed Jam 0.855; Glass Breakage 0.817; Overfill 0.811 |
| FL-04 | Glass Breakage |Glass Breakage | sure | meaning | Glass Breakage 0.864; Infeed Jam 0.818; Overfill 0.799 |
| FL-05 | Product Supply Pressure Low |Product Supply Pressure Low | sure | meaning | Product Supply Pressure Low 0.874; Underfill 0.829; Overfill 0.813 |
| FL-06 | Underfill |Underfill | sure | AI tie-break | Overfill 0.825; Underfill 0.818; Product Supply Pressure Low 0.804 |
| FL-01b | Underfill |Underfill | sure | AI tie-break | Underfill 0.887; Overfill 0.86; Product Supply Pressure Low 0.838 |
| FL-02b | Overfill |Overfill | sure | AI tie-break | Overfill 0.85; Underfill 0.829; Product Supply Pressure Low 0.816 |
| FL-03b | Infeed Jam |Infeed Jam | sure | AI tie-break | Infeed Jam 0.834; Underfill 0.833; Glass Breakage 0.823 |
| FL-04b | Glass Breakage |Glass Breakage | sure | meaning | Glass Breakage 0.886; Underfill 0.786; Infeed Jam 0.785 |
| FL-05b | Product Supply Pressure Low |Product Supply Pressure Low | sure | AI tie-break | Product Supply Pressure Low 0.829; Underfill 0.803; Overfill 0.778 |
| FL-06b | Underfill |Underfill | sure | AI tie-break | Overfill 0.811; Underfill 0.809; Product Supply Pressure Low 0.799 |
| GV-01 | Wire Feed Motor Overload |Wire Feed Motor Overload | sure | meaning | Wire Feed Motor Overload 0.872; Arc Instability 0.797; Contact Tip Temperature High 0.784 |
| GV-02 | Wire Feed Motor Overload |Wire Feed Motor Overload | sure | meaning | Wire Feed Motor Overload 0.842; Arc Instability 0.802; Contact Tip Temperature High 0.778 |
| GV-03 | Wire Feed Motor Overload |Wire Feed Motor Overload | sure | meaning | Wire Feed Motor Overload 0.833; Arc Instability 0.798; Contact Tip Temperature High 0.787 |
| GV-04 | Arc Instability |Arc Instability | sure | meaning | Arc Instability 0.856; Wire Feed Motor Overload 0.796; Contact Tip Temperature High 0.792 |
| GV-05 | Shielding Gas Pressure Low |Shielding Gas Pressure Low | sure | meaning | Shielding Gas Pressure Low 0.821; Arc Instability 0.78; Wire Feed Motor Overload 0.776 |
| GV-06 | Contact Tip Temperature High |Contact Tip Temperature High | sure | meaning | Contact Tip Temperature High 0.863; Arc Instability 0.81; Wire Feed Motor Overload 0.788 |
| WM-e1 | Wire Feed Motor Overload |Wire Feed Motor Overload | sure | meaning | Wire Feed Motor Overload 0.845; Arc Instability 0.807; Contact Tip Temperature High 0.777 |
| WM-e2 | Wire Feed Motor Overload |Wire Feed Motor Overload | sure | meaning + word count agree | Wire Feed Motor Overload 0.833; Arc Instability 0.816; Contact Tip Temperature High 0.785 |
| WM-e3 | Arc Instability |Arc Instability | sure | meaning | Arc Instability 0.846; Contact Tip Temperature High 0.783; Wire Feed Motor Overload 0.781 |
| WM-e4 | Arc Instability |Arc Instability | sure | meaning | Arc Instability 0.819; Wire Feed Motor Overload 0.761; Contact Tip Temperature High 0.757 |
| WM-e5 | Contact Tip Temperature High |Contact Tip Temperature High | sure | AI tie-break | Contact Tip Temperature High 0.825; Arc Instability 0.796; Wire Feed Motor Overload 0.782 |
| WM-e6 | Contact Tip Temperature High |Contact Tip Temperature High | sure | meaning | Contact Tip Temperature High 0.824; Arc Instability 0.789; Wire Feed Motor Overload 0.776 |
| WM-e7 | Shielding Gas Pressure Low |Shielding Gas Pressure Low | sure | meaning | Shielding Gas Pressure Low 0.803; Arc Instability 0.747; Contact Tip Temperature High 0.745 |
| WM-e8 | Shielding Gas Pressure Low |Shielding Gas Pressure Low | sure | meaning | Shielding Gas Pressure Low 0.818; Arc Instability 0.784; Wire Feed Motor Overload 0.772 |
| FL-f1 | Underfill |Underfill | sure | meaning | Underfill 0.867; Overfill 0.829; Product Supply Pressure Low 0.82 |
| FL-f2 | Overfill |Overfill | sure | AI tie-break | Overfill 0.828; Underfill 0.813; Infeed Jam 0.791 |
| FL-f3 | Infeed Jam |Infeed Jam | sure | meaning | Infeed Jam 0.865; Overfill 0.822; Underfill 0.82 |
| FL-f4 | Glass Breakage |Glass Breakage | sure | meaning | Glass Breakage 0.846; Infeed Jam 0.804; Overfill 0.799 |
| FL-f5 | Product Supply Pressure Low |Product Supply Pressure Low | sure | meaning | Product Supply Pressure Low 0.895; Underfill 0.836; Overfill 0.828 |
| FL-f6 | Underfill |Underfill | sure | AI tie-break | Overfill 0.824; Underfill 0.819; Product Supply Pressure Low 0.812 |
| FL-f7 | Infeed Jam |Infeed Jam | sure | AI tie-break | Infeed Jam 0.808; Overfill 0.802; Underfill 0.788 |
| T-1 | Underfill |Underfill | sure | AI tie-break | Overfill 0.866; Underfill 0.86; Product Supply Pressure Low 0.851 |
| T-2 | Underfill |Underfill | sure | AI tie-break | Underfill 0.798; Overfill 0.795; Product Supply Pressure Low 0.792 |
| T-3 | Underfill |Underfill | sure | AI tie-break | Overfill 0.836; Underfill 0.83; Infeed Jam 0.819 |
| FR-01 | none |— | none | AI: none of these faults | Overfill 0.791; Underfill 0.786; Infeed Jam 0.785 |
| FR-02 | Underfill |Underfill | sure | AI tie-break | Underfill 0.857; Overfill 0.844; Product Supply Pressure Low 0.816 |
| FR-03 | Underfill |Underfill | sure | meaning | Underfill 0.832; Overfill 0.795; Infeed Jam 0.794 |
| FR-04 | Infeed Jam or none |— | none | AI: none of these faults | Underfill 0.797; Infeed Jam 0.79; Product Supply Pressure Low 0.785 |
| FR-05 | none |— | none | AI: none of these faults | Underfill 0.792; Overfill 0.787; Infeed Jam 0.772 |