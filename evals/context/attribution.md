# Where missed facts got lost (Context chapter, C1)

Made by `evals/context_attribution.py` from saved runs. No AI calls.
Each missed required fact is followed along documents → search → specialist → writer, and counted at the FIRST hand-off where it went missing.

## Headline

| Where it got lost | Evals teaching set (FL-101) | FL-101 graph value test | WM-101 graph value test (trust order) | Fresh FL-101 questions (graph chapter) | C2 before (teaching, writer gets summaries only) | C2 after (teaching, writer also gets the pieces) | All |
|---|---|---|---|---|---|---|---|
| in report, marked missed (read by hand) | 0 | 0 | 0 | 6 | 0 | 0 | **6** |
| reached the writer, left out | 2 | 7 | 3 | 16 | 3 | 2 | **33** |
| not in the documents | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| not searched (router) | 0 | 3 | 0 | 9 | 0 | 0 | **12** |
| searched, not found (ranking) | 12 | 12 | 0 | 22 | 12 | 12 | **70** |
| found but cut | 0 | 24 | 0 | 0 | 0 | 0 | **24** |
| found, summarised away | 9 | 12 | 0 | 24 | 7 | 0 | **52** |
| found, summarised away, and the evidence cap left the piece out (C2) | 0 | 0 | 0 | 0 | 0 | 5 | **5** |
| not lost: the check marked a correct answer wrong (by hand) | 0 | 1 | 1 | 0 | 0 | 0 | **2** |
| **Marked missed / required facts scored** | 23/80 | 59/132 | 4/66 | 77/132 | 22/36 | 19/40 | **204/486** |
| **Really lost (after hand reading)** | 23 | 58 | 3 | 71 | 22 | 19 | **196** |

## By graph arm

| Arm | in report, marked missed (read by hand) | reached the writer, left out | not in the documents | not searched (router) | searched, not found (ranking) | found but cut | found, summarised away | found, summarised away, and the evidence cap left the piece out (C2) | not lost: the check marked a correct answer wrong (by hand) |
|---|---|---|---|---|---|---|---|---|---|
| graph OFF | 6 | 9 | 0 | 12 | 61 | 24 | 52 | 5 | 1 |
| graph ON | 0 | 24 | 0 | 0 | 9 | 0 | 0 | 0 | 1 |

## Every missed fact

| Suite | Case | Graph | Run | Fact | Lost at | Evidence |
|---|---|---|---|---|---|---|
| teaching | T-1 | off | 1 | L1 check the valves for drips (a drip means a worn seal) | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching | T-1 | off | 1 | L2 a good bottle is 495 to 505 ml | found, summarised away | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching | T-1 | off | 1 | L4 weigh the first 20 bottles after the fix | found, summarised away | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching | T-1 | off | 2 | L2 a good bottle is 495 to 505 ml | found, summarised away | in: NCR, SOP, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching | T-1 | off | 2 | L4 weigh the first 20 bottles after the fix | found, summarised away | in: SOP, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching | T-1 | off | 3 | L1 check the valves for drips (a drip means a worn seal) | reached the writer, left out | **by hand** (script said: in report, marked missed (read by hand)): Drips appear only in the preventive action ('add a daily pre-start check for valve drip signs'), not as the check to make now. Judge right; the writer had the fact and placed it as prevention. |
| teaching | T-1 | off | 3 | L2 a good bottle is 495 to 505 ml | found, summarised away | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching | T-1 | off | 3 | L4 weigh the first 20 bottles after the fix | found, summarised away | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching | T-2 | off | 1 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching | T-2 | off | 1 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching | T-2 | off | 2 | L1 check the valves for drips (a drip means a worn seal) | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching | T-2 | off | 2 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: - |
| teaching | T-2 | off | 2 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: - |
| teaching | T-2 | off | 3 | L1 check the valves for drips (a drip means a worn seal) | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching | T-2 | off | 3 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching | T-2 | off | 3 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching | T-3 | off | 1 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: - |
| teaching | T-3 | off | 1 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: - |
| teaching | T-3 | off | 2 | L1 check the valves for drips (a drip means a worn seal) | reached the writer, left out | **by hand** (script said: in report, marked missed (read by hand)): Drips appear only in the permanent-fix criteria ('dripping, 3+ under-fills'), not as the check to make now. Judge right; the writer had the fact and placed it as prevention. |
| teaching | T-3 | off | 2 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: - |
| teaching | T-3 | off | 2 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: - |
| teaching | T-3 | off | 3 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching | T-3 | off | 3 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| fl101 | FL-01 | off | 1 | allowed fill range 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance, NCR; found by: - |
| fl101 | FL-01 | off | 1 | 10-minute sanitation rinse after the seal change | found but cut | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance, NCR; found by: NCR; given to: - |
| fl101 | FL-01 | off | 1 | weigh the first 20 bottles | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance, NCR; found by: - |
| fl101 | FL-01 | off | 2 | allowed fill range 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Alarm, Maintenance, NCR, Expert Fix; found by: - |
| fl101 | FL-01 | off | 2 | 10-minute sanitation rinse after the seal change | found but cut | in: NCR, SOP, Shift Log, Work Instruction; searched: Alarm, Maintenance, NCR, Expert Fix; found by: NCR; given to: - |
| fl101 | FL-01 | off | 2 | weigh the first 20 bottles | searched, not found (ranking) | in: SOP, Work Instruction; searched: Alarm, Maintenance, NCR, Expert Fix; found by: - |
| fl101 | FL-01 | off | 3 | allowed fill range 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance, NCR; found by: - |
| fl101 | FL-01 | off | 3 | 10-minute sanitation rinse after the seal change | found but cut | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance, NCR; found by: NCR; given to: - |
| fl101 | FL-01 | off | 3 | weigh the first 20 bottles | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance, NCR; found by: - |
| fl101 | FL-02 | off | 1 | Does the report say that slight overfill in the first 2 to 3 minutes after a seal change is expected or normal, not a fault? | found but cut | in: Shift Log, Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: Maintenance; given to: - |
| fl101 | FL-02 | off | 1 | Does the report tell the operator not to change any settings (such as the fill time) because of this overfill? | found but cut | in: Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: Maintenance; given to: - |
| fl101 | FL-02 | off | 1 | first 20 bottles within 495 to 505 ml | found but cut | in: SOP, Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: Maintenance; given to: - |
| fl101 | FL-02 | off | 2 | Does the report say that slight overfill in the first 2 to 3 minutes after a seal change is expected or normal, not a fault? | found but cut | in: Shift Log, Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: Maintenance; given to: - |
| fl101 | FL-02 | off | 2 | Does the report tell the operator not to change any settings (such as the fill time) because of this overfill? | found but cut | in: Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: Maintenance; given to: - |
| fl101 | FL-02 | off | 2 | first 20 bottles within 495 to 505 ml | found but cut | in: SOP, Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: Maintenance; given to: - |
| fl101 | FL-02 | off | 3 | Does the report say that slight overfill in the first 2 to 3 minutes after a seal change is expected or normal, not a fault? | found but cut | in: Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: - |
| fl101 | FL-02 | off | 3 | Does the report tell the operator not to change any settings (such as the fill time) because of this overfill? | found but cut | in: Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: - |
| fl101 | FL-02 | off | 3 | 10-minute sanitation rinse | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Alarm, Maintenance; given to: Maintenance |
| fl101 | FL-02 | off | 3 | first 20 bottles within 495 to 505 ml | found but cut | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: - |
| fl101 | FL-03 | off | 1 | Does the report identify guide rails not reset after the bottle size changeover as the likely cause? | found, summarised away | in: SOP, Shift Log; searched: Expert Fix, Maintenance, Alarm; found by: Alarm; given to: Alarm |
| fl101 | FL-03 | off | 1 | rails to position B for 330 ml | found, summarised away | in: SOP, Shift Log; searched: Expert Fix, Maintenance, Alarm; found by: Alarm; given to: Alarm |
| fl101 | FL-03 | off | 1 | restart at 60 bottles per minute for 2 minutes | found, summarised away | in: SOP, Shift Log; searched: Expert Fix, Maintenance, Alarm; found by: Alarm; given to: Alarm |
| fl101 | FL-03 | off | 2 | Does the report identify guide rails not reset after the bottle size changeover as the likely cause? | found, summarised away | in: SOP, Shift Log; searched: Alarm, Expert Fix, Maintenance; found by: Alarm; given to: Alarm |
| fl101 | FL-03 | off | 2 | rails to position B for 330 ml | found, summarised away | in: SOP, Shift Log; searched: Alarm, Expert Fix, Maintenance; found by: Alarm; given to: Alarm |
| fl101 | FL-03 | off | 2 | restart at 60 bottles per minute for 2 minutes | found, summarised away | in: SOP, Shift Log; searched: Alarm, Expert Fix, Maintenance; found by: Alarm; given to: Alarm |
| fl101 | FL-03 | off | 3 | Does the report identify guide rails not reset after the bottle size changeover as the likely cause? | found, summarised away | in: SOP, Shift Log; searched: Alarm, Maintenance, Expert Fix; found by: Alarm; given to: Alarm |
| fl101 | FL-03 | off | 3 | rails to position B for 330 ml | found, summarised away | in: SOP, Shift Log; searched: Alarm, Maintenance, Expert Fix; found by: Alarm; given to: Alarm |
| fl101 | FL-03 | off | 3 | Does the report say to stop and lock out the machine before clearing the jam, never reaching in while it runs? | not lost: the check marked a correct answer wrong (by hand) | **by hand** (script said: in report, marked missed (read by hand)): Report Step 1: 'Safety - Apply LOTO, stop the line, isolate power' before clearing the jam. The judge said NO; it should be YES. |
| fl101 | FL-03 | off | 3 | restart at 60 bottles per minute for 2 minutes | found, summarised away | in: SOP, Shift Log; searched: Alarm, Maintenance, Expert Fix; found by: Alarm; given to: Alarm |
| fl101 | FL-04 | off | 1 | Does the report say to stop the line at once with the emergency stop? | found but cut | in: SOP, Shift Log; searched: Expert Fix, Alarm, SOP; found by: SOP; given to: - |
| fl101 | FL-04 | off | 1 | hold bottles from the last 30 minutes | found but cut | in: SOP; searched: Expert Fix, Alarm, SOP; found by: SOP; given to: - |
| fl101 | FL-04 | off | 1 | Does the report say to clean up with a vacuum or the glass kit and never with compressed air? | found but cut | in: SOP, Shift Log; searched: Expert Fix, Alarm, SOP; found by: Alarm, SOP; given to: - |
| fl101 | FL-04 | off | 1 | Does the report say the quality lead must sign off before the line restarts? | found but cut | in: SOP, Shift Log; searched: Expert Fix, Alarm, SOP; found by: Alarm, SOP; given to: - |
| fl101 | FL-04 | off | 2 | Does the report say to stop the line at once with the emergency stop? | found but cut | in: SOP, Shift Log; searched: Alarm, Expert Fix, SOP; found by: SOP; given to: - |
| fl101 | FL-04 | off | 2 | hold bottles from the last 30 minutes | found but cut | in: SOP; searched: Alarm, Expert Fix, SOP; found by: SOP; given to: - |
| fl101 | FL-04 | off | 2 | Does the report say to clean up with a vacuum or the glass kit and never with compressed air? | found but cut | in: SOP, Shift Log; searched: Alarm, Expert Fix, SOP; found by: Alarm, SOP; given to: - |
| fl101 | FL-04 | off | 2 | Does the report say the quality lead must sign off before the line restarts? | found but cut | in: SOP, Shift Log; searched: Alarm, Expert Fix, SOP; found by: Alarm, SOP; given to: - |
| fl101 | FL-04 | off | 3 | Does the report say to stop the line at once with the emergency stop? | found but cut | in: SOP, Shift Log; searched: Expert Fix, Maintenance, SOP, Alarm; found by: SOP; given to: - |
| fl101 | FL-04 | off | 3 | hold bottles from the last 30 minutes | found but cut | in: SOP; searched: Expert Fix, Maintenance, SOP, Alarm; found by: SOP; given to: - |
| fl101 | FL-04 | off | 3 | Does the report say to clean up with a vacuum or the glass kit and never with compressed air? | found but cut | in: SOP, Shift Log; searched: Expert Fix, Maintenance, SOP, Alarm; found by: SOP, Alarm; given to: - |
| fl101 | FL-04 | off | 3 | Does the report say the quality lead must sign off before the line restarts? | found but cut | in: SOP, Shift Log; searched: Expert Fix, Maintenance, SOP, Alarm; found by: SOP, Alarm; given to: - |
| fl101 | FL-05 | off | 1 | normal range 1.5 to 2.0 bar | not searched (router) | in: SOP; searched: Expert Fix, Alarm, Maintenance |
| fl101 | FL-05 | off | 1 | Does the report say to clean or replace the supply filter? | found, summarised away | in: SOP, Shift Log; searched: Expert Fix, Alarm, Maintenance; found by: Alarm; given to: Alarm |
| fl101 | FL-05 | off | 1 | Does the report say to bleed air from the supply line? | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm, Maintenance; found by: - |
| fl101 | FL-05 | off | 1 | weigh the first 20 bottles after restart | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| fl101 | FL-05 | off | 2 | normal range 1.5 to 2.0 bar | not searched (router) | in: SOP; searched: Alarm, Expert Fix, Maintenance |
| fl101 | FL-05 | off | 2 | Does the report say to clean or replace the supply filter? | found, summarised away | in: SOP, Shift Log; searched: Alarm, Expert Fix, Maintenance; found by: Alarm; given to: Alarm |
| fl101 | FL-05 | off | 2 | Does the report say to bleed air from the supply line? | searched, not found (ranking) | in: SOP, Shift Log; searched: Alarm, Expert Fix, Maintenance; found by: - |
| fl101 | FL-05 | off | 2 | weigh the first 20 bottles after restart | searched, not found (ranking) | in: SOP, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: - |
| fl101 | FL-05 | off | 3 | normal range 1.5 to 2.0 bar | not searched (router) | in: SOP; searched: Expert Fix, Alarm, Maintenance |
| fl101 | FL-05 | off | 3 | Does the report say to bleed air from the supply line? | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm, Maintenance; found by: - |
| fl101 | FL-05 | off | 3 | weigh the first 20 bottles after restart | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| fl101 | FL-01 | on | 3 | 10-minute sanitation rinse after the seal change | reached the writer, left out |  |
| fl101 | FL-02 | on | 1 | 10-minute sanitation rinse | reached the writer, left out |  |
| fl101 | FL-02 | on | 2 | 10-minute sanitation rinse | reached the writer, left out |  |
| fl101 | FL-02 | on | 3 | 10-minute sanitation rinse | reached the writer, left out |  |
| fl101 | FL-03 | on | 1 | rails to position B for 330 ml | reached the writer, left out |  |
| fl101 | FL-03 | on | 1 | restart at 60 bottles per minute for 2 minutes | reached the writer, left out |  |
| fl101 | FL-03 | on | 2 | restart at 60 bottles per minute for 2 minutes | reached the writer, left out |  |
| trust | GV-05 | on | 2 | Does the report say to stop welding immediately? | reached the writer, left out |  |
| trust | GV-06 | on | 2 | stickout 10-15 mm | reached the writer, left out |  |
| trust | GV-06 | on | 2 | hand-tight + quarter turn | not lost: the check marked a correct answer wrong (by hand) | **by hand** (script said: reached the writer, left out): Report: 'Tighten by hand then add a quarter-turn; do not over-tighten'. Correct; the word check only accepts 'hand-tight'. |
| trust | GV-06 | on | 3 | stickout 10-15 mm | reached the writer, left out |  |
| fresh | FR-01 | on | 1 | checkweigher test bottles 490 and 510 ml before starting | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm, Maintenance, SOP; found by: - |
| fresh | FR-01 | on | 1 | 10-minute sanitation rinse (stopped more than 4 hours) | searched, not found (ranking) | in: SOP; searched: Expert Fix, Alarm, Maintenance, SOP; found by: - |
| fresh | FR-01 | on | 1 | first 20 bottles all 495 to 505 ml | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance, SOP; found by: - |
| fresh | FR-01 | on | 1 | then raise to 120 bottles per minute | reached the writer, left out | writer got it from: graph |
| fresh | FR-01 | on | 2 | checkweigher test bottles 490 and 510 ml before starting | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm, Maintenance, SOP; found by: - |
| fresh | FR-01 | on | 2 | 10-minute sanitation rinse (stopped more than 4 hours) | searched, not found (ranking) | in: SOP; searched: Expert Fix, Alarm, Maintenance, SOP; found by: - |
| fresh | FR-01 | on | 2 | first 20 bottles all 495 to 505 ml | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance, SOP; found by: - |
| fresh | FR-01 | on | 2 | then raise to 120 bottles per minute | reached the writer, left out | writer got it from: graph |
| fresh | FR-01 | on | 3 | checkweigher test bottles 490 and 510 ml before starting | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm, Maintenance, SOP; found by: - |
| fresh | FR-01 | on | 3 | 10-minute sanitation rinse (stopped more than 4 hours) | searched, not found (ranking) | in: SOP; searched: Expert Fix, Alarm, Maintenance, SOP; found by: - |
| fresh | FR-01 | on | 3 | start at 60 bottles per minute | reached the writer, left out | writer got it from: graph |
| fresh | FR-01 | on | 3 | first 20 bottles all 495 to 505 ml | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance, SOP; found by: - |
| fresh | FR-01 | on | 3 | then raise to 120 bottles per minute | reached the writer, left out | writer got it from: graph |
| fresh | FR-02 | on | 2 | check the product supply pressure | reached the writer, left out | writer got it from: SOP, graph |
| fresh | FR-04 | on | 1 | record the changeover; the shift lead signs | reached the writer, left out | writer got it from: Alarm, graph |
| fresh | FR-04 | on | 2 | run 20 bottles at 60 bottles per minute | reached the writer, left out | writer got it from: graph |
| fresh | FR-05 | on | 1 | check for a missing O-ring; fit a new one | reached the writer, left out | writer got it from: graph |
| fresh | FR-05 | on | 1 | valve work is for trained maintenance technicians only | reached the writer, left out | writer got it from: graph |
| fresh | FR-05 | on | 1 | seal kit SEAL-FV-24 (holds the O-ring) | reached the writer, left out | writer got it from: graph |
| fresh | FR-05 | on | 1 | food-grade lubricant FGL-1 only | reached the writer, left out | writer got it from: graph |
| fresh | FR-05 | on | 2 | valve work is for trained maintenance technicians only | reached the writer, left out | writer got it from: graph |
| fresh | FR-05 | on | 3 | check for a missing O-ring; fit a new one | reached the writer, left out | writer got it from: graph |
| fresh | FR-05 | on | 3 | valve work is for trained maintenance technicians only | reached the writer, left out | writer got it from: graph |
| fresh | FR-01 | off | 1 | checkweigher test bottles 490 and 510 ml before starting | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm; found by: - |
| fresh | FR-01 | off | 1 | 10-minute sanitation rinse (stopped more than 4 hours) | not searched (router) | in: SOP; searched: Expert Fix, Alarm |
| fresh | FR-01 | off | 1 | start at 60 bottles per minute | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm; found by: - |
| fresh | FR-01 | off | 1 | first 20 bottles all 495 to 505 ml | not searched (router) | in: SOP, Work Instruction; searched: Expert Fix, Alarm |
| fresh | FR-01 | off | 1 | then raise to 120 bottles per minute | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm; found by: - |
| fresh | FR-01 | off | 2 | checkweigher test bottles 490 and 510 ml before starting | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm; found by: - |
| fresh | FR-01 | off | 2 | 10-minute sanitation rinse (stopped more than 4 hours) | not searched (router) | in: SOP; searched: Expert Fix, Alarm |
| fresh | FR-01 | off | 2 | start at 60 bottles per minute | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm; found by: - |
| fresh | FR-01 | off | 2 | first 20 bottles all 495 to 505 ml | not searched (router) | in: SOP, Work Instruction; searched: Expert Fix, Alarm |
| fresh | FR-01 | off | 2 | then raise to 120 bottles per minute | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm; found by: - |
| fresh | FR-01 | off | 3 | checkweigher test bottles 490 and 510 ml before starting | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm; found by: - |
| fresh | FR-01 | off | 3 | 10-minute sanitation rinse (stopped more than 4 hours) | not searched (router) | in: SOP; searched: Expert Fix, Alarm |
| fresh | FR-01 | off | 3 | start at 60 bottles per minute | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm; found by: - |
| fresh | FR-01 | off | 3 | first 20 bottles all 495 to 505 ml | not searched (router) | in: SOP, Work Instruction; searched: Expert Fix, Alarm |
| fresh | FR-01 | off | 3 | then raise to 120 bottles per minute | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm; found by: - |
| fresh | FR-02 | off | 1 | check the product supply pressure | found, summarised away | in: SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| fresh | FR-02 | off | 2 | no drip means a blocked nozzle: clean it | in report, marked missed (read by hand) |  |
| fresh | FR-02 | off | 2 | check the product supply pressure | found, summarised away | in: SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| fresh | FR-02 | off | 3 | no drip means a blocked nozzle: clean it | in report, marked missed (read by hand) |  |
| fresh | FR-02 | off | 3 | check the product supply pressure | found, summarised away | in: SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| fresh | FR-03 | off | 1 | more than 1 in 100 rejected over an hour: tell the shift lead | found, summarised away | in: SOP, Shift Log; searched: Expert Fix, Alarm, NCR, Maintenance; found by: Alarm; given to: Alarm |
| fresh | FR-03 | off | 1 | bottles must be 495 to 505 ml | reached the writer, left out | writer got it from: NCR |
| fresh | FR-03 | off | 2 | more than 1 in 100 rejected over an hour: tell the shift lead | found, summarised away | in: SOP, Shift Log; searched: Expert Fix, Alarm, Maintenance, NCR; found by: Alarm; given to: Alarm |
| fresh | FR-03 | off | 2 | bottles must be 495 to 505 ml | found, summarised away | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance, NCR; found by: NCR; given to: NCR |
| fresh | FR-03 | off | 3 | more than 1 in 100 rejected over an hour: tell the shift lead | found, summarised away | in: SOP, Shift Log; searched: Expert Fix, Maintenance, Alarm, NCR; found by: Alarm; given to: Alarm |
| fresh | FR-03 | off | 3 | check the fill valves for dripping | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Maintenance, Alarm, NCR; found by: Maintenance, Alarm, NCR; given to: Maintenance, Alarm, NCR |
| fresh | FR-03 | off | 3 | bottles must be 495 to 505 ml | found, summarised away | in: NCR, SOP, Work Instruction; searched: Expert Fix, Maintenance, Alarm, NCR; found by: NCR; given to: NCR |
| fresh | FR-04 | off | 1 | lock out the machine first | in report, marked missed (read by hand) |  |
| fresh | FR-04 | off | 1 | guide rails to position B for 330 ml | found, summarised away | in: SOP, Shift Log; searched: Expert Fix, Alarm, Maintenance; found by: Alarm; given to: Alarm |
| fresh | FR-04 | off | 1 | fit the matching star wheel | not searched (router) | in: SOP; searched: Expert Fix, Alarm, Maintenance |
| fresh | FR-04 | off | 1 | run 20 bottles at 60 bottles per minute | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Alarm, Maintenance; found by: - |
| fresh | FR-04 | off | 1 | record the changeover; the shift lead signs | in report, marked missed (read by hand) |  |
| fresh | FR-04 | off | 2 | lock out the machine first | in report, marked missed (read by hand) |  |
| fresh | FR-04 | off | 2 | guide rails to position B for 330 ml | found, summarised away | in: SOP, Shift Log; searched: Alarm, Expert Fix; found by: Alarm; given to: Alarm |
| fresh | FR-04 | off | 2 | fit the matching star wheel | not searched (router) | in: SOP; searched: Alarm, Expert Fix |
| fresh | FR-04 | off | 2 | run 20 bottles at 60 bottles per minute | searched, not found (ranking) | in: SOP, Shift Log; searched: Alarm, Expert Fix; found by: - |
| fresh | FR-04 | off | 2 | record the changeover; the shift lead signs | reached the writer, left out | writer got it from: Alarm |
| fresh | FR-04 | off | 3 | lock out the machine first | in report, marked missed (read by hand) |  |
| fresh | FR-04 | off | 3 | guide rails to position B for 330 ml | found, summarised away | in: SOP, Shift Log; searched: Expert Fix, Maintenance, Alarm; found by: Alarm; given to: Alarm |
| fresh | FR-04 | off | 3 | fit the matching star wheel | not searched (router) | in: SOP; searched: Expert Fix, Maintenance, Alarm |
| fresh | FR-04 | off | 3 | run 20 bottles at 60 bottles per minute | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Maintenance, Alarm; found by: - |
| fresh | FR-04 | off | 3 | record the changeover; the shift lead signs | searched, not found (ranking) | in: SOP, Shift Log; searched: Expert Fix, Maintenance, Alarm; found by: - |
| fresh | FR-05 | off | 1 | check for a missing O-ring; fit a new one | found, summarised away | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| fresh | FR-05 | off | 1 | valve work is for trained maintenance technicians only | found, summarised away | in: Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| fresh | FR-05 | off | 1 | seal kit SEAL-FV-24 (holds the O-ring) | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Alarm, Maintenance; given to: Alarm, Maintenance |
| fresh | FR-05 | off | 1 | food-grade lubricant FGL-1 only | found, summarised away | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| fresh | FR-05 | off | 2 | check for a missing O-ring; fit a new one | found, summarised away | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| fresh | FR-05 | off | 2 | valve work is for trained maintenance technicians only | found, summarised away | in: Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| fresh | FR-05 | off | 2 | seal kit SEAL-FV-24 (holds the O-ring) | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Alarm, Maintenance; given to: Alarm, Maintenance |
| fresh | FR-05 | off | 2 | food-grade lubricant FGL-1 only | found, summarised away | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| fresh | FR-05 | off | 3 | check for a missing O-ring; fit a new one | found, summarised away | in: SOP, Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: Maintenance; given to: Maintenance |
| fresh | FR-05 | off | 3 | valve work is for trained maintenance technicians only | found, summarised away | in: Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: Maintenance; given to: Maintenance |
| fresh | FR-05 | off | 3 | seal kit SEAL-FV-24 (holds the O-ring) | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: Maintenance, Alarm; given to: Maintenance, Alarm |
| fresh | FR-05 | off | 3 | food-grade lubricant FGL-1 only | found, summarised away | in: SOP, Work Instruction; searched: Expert Fix, Maintenance, Alarm; found by: Maintenance; given to: Maintenance |
| teaching_c2_before | T-1 | off | 1 | L1 check the valves for drips (a drip means a worn seal) | reached the writer, left out | **by hand** (script said: in report, marked missed (read by hand)): Grey zone already noted in step 3: Step 2 says 'inspect seal kits... check for drip signs', but not that a drip means a worn seal. Judge's NO kept; the writer had the fact. |
| teaching_c2_before | T-1 | off | 1 | L2 a good bottle is 495 to 505 ml | found, summarised away | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_before | T-1 | off | 1 | L4 weigh the first 20 bottles after the fix | found, summarised away | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_before | T-1 | off | 3 | L1 check the valves for drips (a drip means a worn seal) | reached the writer, left out | **by hand** (script said: in report, marked missed (read by hand)): 'dripping' appears only in the SOURCE DATA list, not as a check to make. Judge right; the writer had the fact and did not use it. |
| teaching_c2_before | T-1 | off | 3 | L2 a good bottle is 495 to 505 ml | found, summarised away | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_before | T-1 | off | 3 | L4 weigh the first 20 bottles after the fix | found, summarised away | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_before | T-2 | off | 1 | L1 check the valves for drips (a drip means a worn seal) | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_before | T-2 | off | 1 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_before | T-2 | off | 1 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_before | T-2 | off | 2 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: - |
| teaching_c2_before | T-2 | off | 2 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: - |
| teaching_c2_before | T-2 | off | 3 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_before | T-2 | off | 3 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_before | T-3 | off | 1 | L1 check the valves for drips (a drip means a worn seal) | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_before | T-3 | off | 1 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_before | T-3 | off | 1 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_before | T-3 | off | 2 | L1 check the valves for drips (a drip means a worn seal) | reached the writer, left out | writer got it from: Alarm, Maintenance |
| teaching_c2_before | T-3 | off | 2 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_before | T-3 | off | 2 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_before | T-3 | off | 3 | L1 check the valves for drips (a drip means a worn seal) | found, summarised away | in: NCR, SOP, Shift Log, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_before | T-3 | off | 3 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_before | T-3 | off | 3 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_after | T-1 | off | 1 | L2 a good bottle is 495 to 505 ml | found, summarised away, and the evidence cap left the piece out (C2) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_after | T-1 | off | 1 | L4 weigh the first 20 bottles after the fix | found, summarised away, and the evidence cap left the piece out (C2) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_after | T-1 | off | 2 | L2 a good bottle is 495 to 505 ml | found, summarised away, and the evidence cap left the piece out (C2) | in: NCR, SOP, Work Instruction; searched: Alarm, Expert Fix, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_after | T-1 | off | 3 | L2 a good bottle is 495 to 505 ml | found, summarised away, and the evidence cap left the piece out (C2) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_after | T-1 | off | 3 | L4 weigh the first 20 bottles after the fix | found, summarised away, and the evidence cap left the piece out (C2) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: Maintenance; given to: Maintenance |
| teaching_c2_after | T-2 | off | 1 | L1 check the valves for drips (a drip means a worn seal) | reached the writer, left out | writer got it from: evidence pieces |
| teaching_c2_after | T-2 | off | 1 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_after | T-2 | off | 1 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_after | T-2 | off | 2 | L1 check the valves for drips (a drip means a worn seal) | reached the writer, left out | writer got it from: evidence pieces |
| teaching_c2_after | T-2 | off | 2 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_after | T-2 | off | 2 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_after | T-2 | off | 3 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Alarm, Maintenance, Expert Fix; found by: - |
| teaching_c2_after | T-2 | off | 3 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Alarm, Maintenance, Expert Fix; found by: - |
| teaching_c2_after | T-3 | off | 1 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_after | T-3 | off | 1 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_after | T-3 | off | 2 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_after | T-3 | off | 2 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_after | T-3 | off | 3 | L2 a good bottle is 495 to 505 ml | searched, not found (ranking) | in: NCR, SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |
| teaching_c2_after | T-3 | off | 3 | L4 weigh the first 20 bottles after the fix | searched, not found (ranking) | in: SOP, Work Instruction; searched: Expert Fix, Alarm, Maintenance; found by: - |

## Not attributed (counted only)

- Said something it must not, or wrong rating: 7
  - fl101 FL-01 graph off run 3: Does the report avoid telling the operator to increase or change the fill time? (A warning NOT to change it counts as YES.) (avoid)
  - fl101 FL-02 graph off run 1: Does the report avoid recommending replacing the seals again as the fix? (avoid)
  - fl101 FL-02 graph off run 1: rated LOW or MEDIUM, not HIGH (rating)
  - fl101 FL-03 graph on run 3: no welding facts from WM-101 (avoid)
  - fresh FR-02 graph off run 1: does NOT tell the operator to turn up the fill time (avoid)
  - fresh FR-03 graph off run 1: does NOT tell the operator to turn up the fill time (avoid)
  - fresh FR-03 graph off run 3: does NOT tell the operator to turn up the fill time (avoid)
- Judge answer missing from the cache (not scored, not re-asked): 0

## Checks on this method

- Evals teaching set (FL-101): repeating the searches today returned the same pieces as saved on the day in **82/82** specialist searches.
- Fresh FL-101 questions (graph chapter): repeating the searches today returned the same pieces as saved on the day in **112/113** specialist searches.
- C2 before (teaching, writer gets summaries only): repeating the searches today returned the same pieces as saved on the day in **28/28** specialist searches.
- C2 after (teaching, writer also gets the pieces): repeating the searches today returned the same pieces as saved on the day in **32/32** specialist searches.
- Runs before 1 Oct: what each specialist received is re-created today (same search wording, old 300-character cut), not recorded on the day.
- Facts are found by word patterns (evals/context/context_facts.json). Rows in 'reached the writer', 'searched, not found' and 'in report, marked missed' are read by hand before any number is used.
