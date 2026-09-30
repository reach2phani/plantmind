# Fault match check — before

Run 2026-09-30 07:37. Matcher: **words**. Right = exactly the expected fault and sure. Unsure = expected fault among the close candidates, flagged. Wrong = anything else.

| Machine | Set | Right | Unsure | Wrong | False CRITICAL |
|---|---|---|---|---|---|
| FL-101 | everyday | 1/6 | 4/6 | 1/6 | 0 |
| FL-101 | user | 3/6 | 1/6 | 2/6 | 0 |
| WM-101 | alarm | 6/6 | 0/6 | 0/6 | 0 |
| WM-101 | everyday | 4/8 | 0/8 | 4/8 | 0 |
| **All** | | **14/26** | 5/26 | 7/26 | 0 |

## Every question

| Id | Expected | Got | Confidence | How | Top scores |
|---|---|---|---|---|---|
| FL-01 | Underfill | Overfill | sure | word count |  |
| FL-02 | Overfill | Underfill, Overfill, Infeed Jam | unsure | word count |  |
| FL-03 | Infeed Jam | Infeed Jam | sure | word count |  |
| FL-04 | Glass Breakage | Glass Breakage | sure | word count |  |
| FL-05 | Product Supply Pressure Low | Product Supply Pressure Low | sure | word count |  |
| FL-06 | Underfill | Overfill | sure | word count |  |
| FL-01b | Underfill | Underfill, Overfill | unsure | word count |  |
| FL-02b | Overfill | Underfill, Overfill | unsure | word count |  |
| FL-03b | Infeed Jam | Infeed Jam, Glass Breakage | unsure | word count |  |
| FL-04b | Glass Breakage | Glass Breakage | sure | word count |  |
| FL-05b | Product Supply Pressure Low | Glass Breakage, Product Supply Pressure Low | unsure | word count |  |
| FL-06b | Underfill | Overfill | sure | word count |  |
| GV-01 | Wire Feed Motor Overload | Wire Feed Motor Overload | sure | word count |  |
| GV-02 | Wire Feed Motor Overload | Wire Feed Motor Overload | sure | word count |  |
| GV-03 | Wire Feed Motor Overload | Wire Feed Motor Overload | sure | word count |  |
| GV-04 | Arc Instability | Arc Instability | sure | word count |  |
| GV-05 | Shielding Gas Pressure Low | Shielding Gas Pressure Low | sure | word count |  |
| GV-06 | Contact Tip Temperature High | Contact Tip Temperature High | sure | word count |  |
| WM-e1 | Wire Feed Motor Overload | Wire Feed Motor Overload | sure | word count |  |
| WM-e2 | Wire Feed Motor Overload | Wire Feed Motor Overload | sure | word count |  |
| WM-e3 | Arc Instability | — | none | word count |  |
| WM-e4 | Arc Instability | — | none | word count |  |
| WM-e5 | Contact Tip Temperature High | — | none | word count |  |
| WM-e6 | Contact Tip Temperature High | Contact Tip Temperature High | sure | word count |  |
| WM-e7 | Shielding Gas Pressure Low | Shielding Gas Pressure Low | sure | word count |  |
| WM-e8 | Shielding Gas Pressure Low | — | none | word count |  |