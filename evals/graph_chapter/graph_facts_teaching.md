# Facts that appear only with the graph (teaching)

Made by `evals/graph_facts_table.py` from saved runs. No AI calls.
Runs: teaching (evals/fl101/results/teaching_runs.jsonl): graph OFF 9 reports, graph ON 11; teaching_c2_before (evals/fl101/results/teaching_c2_before_runs.jsonl): graph OFF 9 reports, graph ON 0.

| Fact | Graph OFF | Graph ON | Where the graph-ON writer could get it | Verdict |
|---|---|---|---|---|
| L1 check the valves for drips (a drip means a worn seal) | 7/18 | 11/11 | graph only 1, both 10 | much more often with the graph |
| L2 a good bottle is 495 to 505 ml | 1/18 | 11/11 | both 11 | much more often with the graph |
| L3 stop the machine and make it safe before touching it | 18/18 | 11/11 | both 11 | no difference |
| L4 weigh the first 20 bottles after the fix | 1/18 | 11/11 | both 11 | much more often with the graph |
| L5 does NOT tell the operator to turn up the fill time | 18/18 | 11/11 | (avoid: a thing the report must NOT say) |  |

How to read it:
- 'graph only' = the fact was in the graph's text and in none of the specialists' summaries.
- Facts are spotted by the word patterns in evals/context/context_facts.json (same as C1); judge-marked facts can be worded differently, so 'neither' rows are worth reading.
