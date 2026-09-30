# Fault match check — tuning

Run 2026-09-30 07:38. Matcher: **no-ai**. Right = exactly the expected fault and sure. Unsure = expected fault among the close candidates, flagged. Wrong = anything else.

| Machine | Set | Right | Unsure | Wrong | False CRITICAL |
|---|---|---|---|---|---|
| FL-101 | everyday | 1/6 | 5/6 | 0/6 | 0 |
| FL-101 | user | 4/6 | 2/6 | 0/6 | 0 |
| WM-101 | alarm | 6/6 | 0/6 | 0/6 | 0 |
| WM-101 | everyday | 7/8 | 1/8 | 0/8 | 0 |
| **All** | | **18/26** | 8/26 | 0/26 | 0 |

## Every question

| Id | Expected | Got | Confidence | How | Top scores |
|---|---|---|---|---|---|
| FL-01 | Underfill | Underfill | sure | meaning | Underfill 0.895; Overfill 0.863; Product Supply Pressure Low 0.836 |
| FL-02 | Overfill | Overfill, Underfill | unsure | close call between faults | Overfill 0.86; Underfill 0.837; Product Supply Pressure Low 0.811 |
| FL-03 | Infeed Jam | Infeed Jam | sure | meaning | Infeed Jam 0.855; Glass Breakage 0.817; Overfill 0.811 |
| FL-04 | Glass Breakage | Glass Breakage | sure | meaning | Glass Breakage 0.864; Infeed Jam 0.818; Overfill 0.799 |
| FL-05 | Product Supply Pressure Low | Product Supply Pressure Low | sure | meaning | Product Supply Pressure Low 0.874; Underfill 0.829; Overfill 0.813 |
| FL-06 | Underfill | Overfill, Underfill, Product Supply Pressure Low | unsure | close call between faults | Overfill 0.825; Underfill 0.818; Product Supply Pressure Low 0.804 |
| FL-01b | Underfill | Underfill, Overfill | unsure | close call between faults | Underfill 0.887; Overfill 0.86; Product Supply Pressure Low 0.838 |
| FL-02b | Overfill | Overfill, Underfill | unsure | close call between faults | Overfill 0.85; Underfill 0.829; Product Supply Pressure Low 0.816 |
| FL-03b | Infeed Jam | Infeed Jam, Underfill, Glass Breakage | unsure | close call between faults | Infeed Jam 0.834; Underfill 0.833; Glass Breakage 0.823 |
| FL-04b | Glass Breakage | Glass Breakage | sure | meaning | Glass Breakage 0.886; Underfill 0.786; Infeed Jam 0.785 |
| FL-05b | Product Supply Pressure Low | Product Supply Pressure Low, Underfill | unsure | close call between faults | Product Supply Pressure Low 0.829; Underfill 0.803; Overfill 0.778 |
| FL-06b | Underfill | Overfill, Underfill, Product Supply Pressure Low | unsure | close call between faults | Overfill 0.811; Underfill 0.809; Product Supply Pressure Low 0.799 |
| GV-01 | Wire Feed Motor Overload | Wire Feed Motor Overload | sure | meaning | Wire Feed Motor Overload 0.872; Arc Instability 0.797; Contact Tip Temperature High 0.784 |
| GV-02 | Wire Feed Motor Overload | Wire Feed Motor Overload | sure | meaning | Wire Feed Motor Overload 0.842; Arc Instability 0.802; Contact Tip Temperature High 0.778 |
| GV-03 | Wire Feed Motor Overload | Wire Feed Motor Overload | sure | meaning | Wire Feed Motor Overload 0.833; Arc Instability 0.798; Contact Tip Temperature High 0.787 |
| GV-04 | Arc Instability | Arc Instability | sure | meaning | Arc Instability 0.856; Wire Feed Motor Overload 0.796; Contact Tip Temperature High 0.792 |
| GV-05 | Shielding Gas Pressure Low | Shielding Gas Pressure Low | sure | meaning | Shielding Gas Pressure Low 0.821; Arc Instability 0.78; Wire Feed Motor Overload 0.776 |
| GV-06 | Contact Tip Temperature High | Contact Tip Temperature High | sure | meaning | Contact Tip Temperature High 0.863; Arc Instability 0.81; Wire Feed Motor Overload 0.788 |
| WM-e1 | Wire Feed Motor Overload | Wire Feed Motor Overload | sure | meaning | Wire Feed Motor Overload 0.845; Arc Instability 0.807; Contact Tip Temperature High 0.777 |
| WM-e2 | Wire Feed Motor Overload | Wire Feed Motor Overload | sure | meaning + word count agree | Wire Feed Motor Overload 0.833; Arc Instability 0.816; Contact Tip Temperature High 0.785 |
| WM-e3 | Arc Instability | Arc Instability | sure | meaning | Arc Instability 0.846; Contact Tip Temperature High 0.783; Wire Feed Motor Overload 0.781 |
| WM-e4 | Arc Instability | Arc Instability | sure | meaning | Arc Instability 0.819; Wire Feed Motor Overload 0.761; Contact Tip Temperature High 0.757 |
| WM-e5 | Contact Tip Temperature High | Contact Tip Temperature High, Arc Instability | unsure | close call between faults | Contact Tip Temperature High 0.825; Arc Instability 0.796; Wire Feed Motor Overload 0.782 |
| WM-e6 | Contact Tip Temperature High | Contact Tip Temperature High | sure | meaning | Contact Tip Temperature High 0.824; Arc Instability 0.789; Wire Feed Motor Overload 0.776 |
| WM-e7 | Shielding Gas Pressure Low | Shielding Gas Pressure Low | sure | meaning | Shielding Gas Pressure Low 0.803; Arc Instability 0.747; Contact Tip Temperature High 0.745 |
| WM-e8 | Shielding Gas Pressure Low | Shielding Gas Pressure Low | sure | meaning | Shielding Gas Pressure Low 0.818; Arc Instability 0.784; Wire Feed Motor Overload 0.772 |