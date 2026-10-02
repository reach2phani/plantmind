# Teaching set — step 7a: each part on its own

Run 2026-10-01 12:14. Same machine finder, fault matcher, searches and routing rule as a real investigation; no report written. The investigation takes the top 4 search pieces scoring 0.4+, and shows the specialist the first 2000 characters of each.

| Part | T-1 | T-2 | T-3 |
|---|---|---|---|
| 1 Machine finder → FL-101 | ✅ FL-101 | ✅ FL-101 | ✅ FL-101 |
| 2 Fault matcher → Underfill | ✅ Underfill (sure) | ✅ Underfill (sure) | ✅ Underfill (sure) |
| 3 Search SOP: "Dripping means a worn seal" (L1) | rank 7 · taken ❌ · shown ✅ | rank 3 · taken ✅ · shown ✅ | rank 10 · taken ❌ · shown ✅ |
| 3 Search Work Instruction: "weigh the first 20 bottles" (L4) | rank 4 · taken ✅ · shown ✅ | rank 8 · taken ❌ · shown ✅ | rank 6 · taken ❌ · shown ✅ |
| 3 Search SOP: "weigh the first 20 bottles" (L4) | rank 2 · taken ✅ · shown ✅ | rank 4 · taken ✅ · shown ✅ | rank 3 · taken ✅ · shown ✅ |
| 4 Graph hand-over: "drips between fills" (L1) | ✅ | ✅ | ✅ |
| 4 Graph hand-over: "weigh the first 20 bottles" (L4) | ✅ | ✅ | ✅ |
| 5 Router: SOP + work instruction required | ✅ alarm, expert_fix, maintenance, sop, ncr | ✅ alarm, expert_fix, maintenance, sop, ncr | ✅ alarm, expert_fix, maintenance, sop, ncr |

## How to read this

- **taken** = the piece is in the top 4 with a score of 0.4+, so the investigation uses it.
- **shown** = the sentence is inside the first 2000 characters of the piece. The specialist never sees anything after that, even when the piece was found.
- A part that fails here can explain a missing line in the real runs (step 7b).
- Three wordings: a direction, not proof.