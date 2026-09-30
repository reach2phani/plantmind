# Fault match check — exam_before

Run 2026-09-30 07:46. Matcher: **words**. Right = exactly the expected fault and sure. Unsure = expected fault among the close candidates, flagged. Wrong = anything else.

| Machine | Set | Right | Unsure | Wrong | False CRITICAL |
|---|---|---|---|---|---|
| FL-101 | fresh | 4/7 | 1/7 | 2/7 | 1 |
| **All** | | **4/7** | 1/7 | 2/7 | 1 |

## Every question

| Id | Expected | Got | Confidence | How | Top scores |
|---|---|---|---|---|---|
| FL-f1 | Underfill | Glass Breakage | sure | word count |  |
| FL-f2 | Overfill | Underfill, Overfill, Infeed Jam, Product Supply Pressure Low | unsure | word count |  |
| FL-f3 | Infeed Jam | Infeed Jam | sure | word count |  |
| FL-f4 | Glass Breakage | Glass Breakage | sure | word count |  |
| FL-f5 | Product Supply Pressure Low | Product Supply Pressure Low | sure | word count |  |
| FL-f6 | Underfill | Overfill | sure | word count |  |
| FL-f7 | Infeed Jam | Infeed Jam | sure | word count |  |