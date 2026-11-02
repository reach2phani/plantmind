# Failure analysis - baseline-v1

**Most serious and most frequent: Missing safety warning (9 failed checks) - lost at AI generation - writer in 7 of them.**

Written 2026-11-02 22:08 UTC. Failure map: `evals/fl101/failure_map.json` (reviewed, 2026-11-02).
Method: Facts followed with key phrases (code). Search replayed in Pinecone (top 15 by meaning, no reranker call); graph rebuilt from Neo4j without the AI tie-break. 0 Groq tokens.

## Level 1 - what went wrong and why it matters

| Severity | What went wrong | Failed checks | Scenarios | Why it matters | Mostly lost at |
|---|---|---|---|---|---|
| 1 Safety | Missing safety warning | 9 | TC2 x3, TC3 x2, TC4 x2, TC5 x2 | Someone could get hurt: the operator is not told what they must never do. | AI generation - writer |
| 1 Safety | Wrong severity rating | 4 | TC1 x2, TC3 x2 | The problem gets less attention than it should (rated below the plant's own floor). | AI generation - writer |
| 2 Quality | Not backed by documents | 8 | TC1 x1, TC2 x1, TC3 x1, TC5 x5 | The operator may follow advice or values that are not the plant's procedure. | AI generation - writer |
| 2 Quality | Missing step | 4 | TC4 x1, TC5 x3 | A required step (rinse, sign-off) is skipped: product or quality risk after the repair. | AI generation - writer |
| 2 Quality | Missing exact value | 3 | TC2 x3 | The operator is told what to check but not the value, so they must hunt for it: slower and easier to get wrong. | AI generation - writer |
| 2 Quality | Steps in the wrong order | 1 | TC5 x1 | Following the steps as written could mean acting before it is safe or before checking. | AI generation - writer |
| 3 Speed / clarity | Hard to read | 5 | TC2 x2, TC4 x2, TC5 x1 | Codes and jargon without plain words: slower and more error-prone for the operator. | Rubric / judge |
| 3 Speed / clarity | Missing helpful detail | 5 | TC2 x2, TC5 x3 | Useful but not required detail is missing (coverage score, not a pass/fail gate). | AI generation - writer |
| 3 Speed / clarity | Part of the question not answered | 1 | TC3 x1 | The operator asked something and has to ask again or guess. | AI generation - writer |

## Level 2 - where in the pipeline

| Step | Failed checks |
|---|---|
| AI generation - writer | 31 |
| Rubric / judge | 7 |
| Source documents | 2 |

## Each traced failure

### TC2 r1 - TS:TC2-rails (Missing exact value)
Fact: Guide rails: position A for 500 ml bottles, position B for 330 ml bottles.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ❌ → Knowledge graph ✅ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (dropped)
- Source documents ✅: FL-101-SOP.txt: "re set for the bottle size being run: 500 ml bottles: rail position A 330 ml bottles: rail position B - Check the rails a"
- Routing (supervisor) ✅: the sop specialist searched SOP
- Chunking ✅: whole in chunk 8
- Embedding + vector search ✅: chunk 8 was #3 of 15 by meaning (score 0.8574)
- Reranking ❌: dropped: not in the 4 chunks handed to the sop specialist
- Knowledge graph ✅: in the graph text: "tting: reference: Changeover sheet CS-FL101; bottle 500 ml: Rail position A; bottle 330 ml: Rail position B; also check: Rails locked a"
- AI generation - writer ❌: had the fact and left it out of the report

### TC2 r1 - SR:safe-TC2-no-reach (Missing safety warning)
Fact: Never reach into the infeed or the star wheel while the machine is running.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ✅ → Context and token limits ✅ → AI generation - specialist ✅ → Knowledge graph ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (dropped) + Knowledge graph (not on the must-show list)
- Source documents ✅: FL-101-SOP.txt: "s 3. Bottle feed conveyor running too fast SAFETY: Never reach into the infeed or the star wheel while the machine is running. Stop the ma"
- Routing (supervisor) ✅: the sop specialist searched SOP
- Chunking ✅: whole in chunk 15
- Embedding + vector search ✅: chunk 15 was #1 of 15 by meaning (score 0.8793)
- Reranking ✅: kept: rank 1 of 4
- Context and token limits ✅: chunk handed over whole; 0 AI call(s) cut off by the token limit
- AI generation - specialist ✅: SOP Agent kept it: "ded for this incident. - Safety requirements: - Never reach into the infeed or star wheel while the machine is running. - Stop the"
- Knowledge graph ⚠: in the graph text, but NOT on the must-show warnings list: "Jam [source: FL-101-SOP Section 12.2] safety rule: Never reach into the infeed or the star wheel while the machine is running. Stop the ma"
- AI generation - writer ❌: had the fact and left it out of the report

### TC3 r1 - SR:safe-TC3-no-early-restart (Missing safety warning)
Fact: Do not restart the filler until the pressure is back to 1.5 to 2.0 bar.  
Path: Source documents ⚠ → Routing (supervisor) – → Knowledge graph ❌ → AI generation - writer –  
**Lost at: Source documents** · component: Source documents (only implied) + AI generation - writer
- Source documents ⚠: only implied, not written: FL-101-SOP Section 12.4 (Steps 4-5) - ONLY IMPLIED by the step order, never written as a prohibition
- Routing (supervisor) –: no document states the fact, nothing to search for
- Knowledge graph ❌: not in the graph text
- AI generation - writer –: never received the fact

### TC5 r1 - TS:TC5-signoff (Missing step)
Fact: The shift supervisor must sign off the first-bottle check before normal production restarts.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ❌ → Knowledge graph ✅ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (in the wrong place)
- Source documents ✅: FL-101-Work-Instruction.txt: "missing? Fit a new O-ring 11. SIGN-OFF - The shift supervisor must sign off the first-bottle check before normal production res"
- Routing (supervisor) ✅: the maintenance specialist searched Work Instruction
- Chunking ✅: whole in chunk 7
- Embedding + vector search ✅: chunk 7 was #3 of 8 by meaning (score 0.864)
- Reranking ❌: dropped: not in the 4 chunks handed to the maintenance specialist
- Knowledge graph ✅: in the graph text: "e, stop and check the valve again. signoff: The shift supervisor signs off the first-bottle check mandatory: true - n"
- AI generation - writer ❌: in the report, but not in the immediate actions: "t checklist to include a “Seal-Change Settling Observation” sign-off by the shift supervisor. • Review seal-change interval compliance (every 3 mont"

### TC2 r2 - TS:TC2-rails (Missing exact value)
Fact: Guide rails: position A for 500 ml bottles, position B for 330 ml bottles.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ❌ → Knowledge graph ✅ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (dropped)
- Source documents ✅: FL-101-SOP.txt: "re set for the bottle size being run: 500 ml bottles: rail position A 330 ml bottles: rail position B - Check the rails a"
- Routing (supervisor) ✅: the sop specialist searched SOP
- Chunking ✅: whole in chunk 8
- Embedding + vector search ✅: chunk 8 was #3 of 15 by meaning (score 0.8574)
- Reranking ❌: dropped: not in the 4 chunks handed to the sop specialist
- Knowledge graph ✅: in the graph text: "tting: reference: Changeover sheet CS-FL101; bottle 500 ml: Rail position A; bottle 330 ml: Rail position B; also check: Rails locked a"
- AI generation - writer ❌: had the fact and left it out of the report

### TC2 r2 - SR:safe-TC2-no-reach (Missing safety warning)
Fact: Never reach into the infeed or the star wheel while the machine is running.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ✅ → Context and token limits ✅ → AI generation - specialist ✅ → Knowledge graph ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (dropped) + Knowledge graph (not on the must-show list)
- Source documents ✅: FL-101-SOP.txt: "s 3. Bottle feed conveyor running too fast SAFETY: Never reach into the infeed or the star wheel while the machine is running. Stop the ma"
- Routing (supervisor) ✅: the sop specialist searched SOP
- Chunking ✅: whole in chunk 15
- Embedding + vector search ✅: chunk 15 was #1 of 15 by meaning (score 0.8793)
- Reranking ✅: kept: rank 1 of 4
- Context and token limits ✅: chunk handed over whole; 0 AI call(s) cut off by the token limit
- AI generation - specialist ✅: SOP Agent kept it: "ed for this incident. - Safety requirements: * Never reach into the infeed or star wheel while the machine is running. * Stop the"
- Knowledge graph ⚠: in the graph text, but NOT on the must-show warnings list: "Jam [source: FL-101-SOP Section 12.2] safety rule: Never reach into the infeed or the star wheel while the machine is running. Stop the ma"
- AI generation - writer ❌: had the fact and left it out of the report

### TC4 r2 - TS:TC4-signoff (Missing step)
Fact: The quality lead must sign off before the line restarts.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ✅ → Context and token limits ✅ → AI generation - specialist ✅ → Knowledge graph ✅ → AI generation - writer ⚠  
**Lost at: Rubric / judge** · component: Rubric / judge: the words are there, please check the verdict
- Source documents ✅: FL-101-SOP.txt: "e the filler (sanitation rinse, 10 minutes). Step 6 - The quality lead must sign off before the line restarts. Step 7 - Record the event i"
- Routing (supervisor) ✅: the sop specialist searched SOP
- Chunking ✅: whole in chunk 16
- Embedding + vector search ✅: chunk 16 was #1 of 15 by meaning (score 0.8933)
- Reranking ✅: kept: rank 1 of 4
- Context and token limits ✅: chunk handed over whole; 0 AI call(s) cut off by the token limit
- AI generation - specialist ✅: SOP Agent kept it: "e filler with a sanitation rinse for 10 minutes. 6. The quality lead must sign off before the line restarts. 7. Record the event in th"
- Knowledge graph ✅: in the graph text: "a vacuum. 5. Run the sanitation rinse (10 minutes). 6. The quality lead signs off before the line restarts. 7. Record the event in the g"
- AI generation - writer ⚠: the words ARE in the immediate actions: "ion rinse of the bowl, valves and nozzles. Step 4: Verify - Quality lead signs off the cleanup; run a short test cycle to confirm no glas" - the judge still failed it

### TC5 r2 - TS:TC5-rinse (Missing step)
Fact: The 10-minute sanitation rinse must be done after the seal change, before normal production.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ✅ → Context and token limits ✅ → AI generation - specialist ❌ → Knowledge graph ✅ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (in the wrong place)
- Source documents ✅: FL-101-SOP.txt: "ntil the quality lead has checked it". Sanitation rinse A 10-minute rinse of the bowl, valves and nozzles with"; FL-101-Work-Instruction.txt: "Remove the lock and refill the bowl. Step 9 - SANITATION RINSE - MANDATORY Run the sanitation rinse for 10 minu"
- Routing (supervisor) ✅: the maintenance specialist searched Work Instruction
- Chunking ✅: whole in chunk 4
- Embedding + vector search ✅: chunk 4 was #5 of 8 by meaning (score 0.8588)
- Reranking ✅: kept: rank 3 of 4
- Context and token limits ✅: chunk handed over whole; 0 AI call(s) cut off by the token limit
- AI generation - specialist ❌: Maintenance Agent read it but left it out of its finding
- Knowledge graph ✅: in the graph text and on the must-show warnings list: "tion must not restart without it then required: Sanitation Rinse [source: WI-FL101-001 Step 9, FL-101-SOP Sections 4, 9, 12"
- AI generation - writer ❌: in the report, but not in the immediate actions: "hange work instruction requiring the First-Bottle Check and Sanitation Rinse before normal production. (KG, WI-FL101-001) • Train oper"

### TC5 r2 - SR:safe-TC5-no-settings (Missing safety warning)
Fact: Do not change any settings for the short overfill after a seal change - it is expected behaviour.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ✅ → Context and token limits ✅ → AI generation - specialist ❌ → Knowledge graph ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (dropped) + Knowledge graph (not on the must-show list)
- Source documents ✅: FL-101-Work-Instruction.txt: "new seals settle. This is EXPECTED BEHAVIOUR - not a fault. Do not change any settings. The checkweigher rejects these bottles automatically. 9."
- Routing (supervisor) ✅: the maintenance specialist searched Work Instruction
- Chunking ✅: whole in chunk 4
- Embedding + vector search ✅: chunk 4 was #5 of 8 by meaning (score 0.8588)
- Reranking ✅: kept: rank 3 of 4
- Context and token limits ✅: chunk handed over whole; 0 AI call(s) cut off by the token limit
- AI generation - specialist ❌: Maintenance Agent read it but left it out of its finding
- Knowledge graph ⚠: in the graph text, but NOT on the must-show warnings list: "n 2 to 3 minutes, it is normal settling: take no action and do not change any settings. causes in order: 1. New seals settling in the first 2 t"
- AI generation - writer ❌: had the fact and left it out of the report

### TC5 r2 - SR:safe-graph-donots-shown (Missing safety warning)
Fact: Every 'Do NOT' warning from the knowledge graph is told to the operator in the immediate actions.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ✅ → Context and token limits ✅ → AI generation - specialist ❌ → Knowledge graph ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (dropped) + Knowledge graph (not on the must-show list)
- Source documents ✅: FL-101-Work-Instruction.txt: "new seals settle. This is EXPECTED BEHAVIOUR - not a fault. Do not change any settings. The checkweigher rejects these bottles automatically. 9."
- Routing (supervisor) ✅: the maintenance specialist searched Work Instruction
- Chunking ✅: whole in chunk 4
- Embedding + vector search ✅: chunk 4 was #5 of 8 by meaning (score 0.8588)
- Reranking ✅: kept: rank 3 of 4
- Context and token limits ✅: chunk handed over whole; 0 AI call(s) cut off by the token limit
- AI generation - specialist ❌: Maintenance Agent read it but left it out of its finding
- Knowledge graph ⚠: in the graph text, but NOT on the must-show warnings list: "n 2 to 3 minutes, it is normal settling: take no action and do not change any settings. causes in order: 1. New seals settling in the first 2 t"
- AI generation - writer ❌: had the fact and left it out of the report

### TC1 r3 - OQ:criticality-exact (Wrong severity rating)
Path: Knowledge graph ✅ → Knowledge graph ⚠ → Report rules (guardrail) ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (chose the rating) + Report rules (no floor for this fault)
- Knowledge graph ✅: matched fault: Underfill (sure)
- Knowledge graph ⚠: the graph gives NO rating for this fault
- Report rules (guardrail) ⚠: no floor: the guardrail only enforces CRITICAL faults
- AI generation - writer ❌: rated MEDIUM, expected HIGH

### TC1 r3 - SR:safe-criticality-floor (Wrong severity rating)
Path: Knowledge graph ✅ → Knowledge graph ⚠ → Report rules (guardrail) ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (chose the rating) + Report rules (no floor for this fault)
- Knowledge graph ✅: matched fault: Underfill (sure)
- Knowledge graph ⚠: the graph gives NO rating for this fault
- Report rules (guardrail) ⚠: no floor: the guardrail only enforces CRITICAL faults
- AI generation - writer ❌: rated MEDIUM, expected HIGH

### TC2 r3 - TS:TC2-rails (Missing exact value)
Fact: Guide rails: position A for 500 ml bottles, position B for 330 ml bottles.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ❌ → Knowledge graph ✅ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (dropped)
- Source documents ✅: FL-101-SOP.txt: "re set for the bottle size being run: 500 ml bottles: rail position A 330 ml bottles: rail position B - Check the rails a"
- Routing (supervisor) ✅: the sop specialist searched SOP
- Chunking ✅: whole in chunk 8
- Embedding + vector search ✅: chunk 8 was #3 of 15 by meaning (score 0.8574)
- Reranking ❌: dropped: not in the 4 chunks handed to the sop specialist
- Knowledge graph ✅: in the graph text: "tting: reference: Changeover sheet CS-FL101; bottle 500 ml: Rail position A; bottle 330 ml: Rail position B; also check: Rails locked a"
- AI generation - writer ❌: had the fact and left it out of the report

### TC2 r3 - SR:safe-TC2-no-reach (Missing safety warning)
Fact: Never reach into the infeed or the star wheel while the machine is running.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ✅ → Context and token limits ✅ → AI generation - specialist ✅ → Knowledge graph ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (dropped) + Knowledge graph (not on the must-show list)
- Source documents ✅: FL-101-SOP.txt: "s 3. Bottle feed conveyor running too fast SAFETY: Never reach into the infeed or the star wheel while the machine is running. Stop the ma"
- Routing (supervisor) ✅: the sop specialist searched SOP
- Chunking ✅: whole in chunk 15
- Embedding + vector search ✅: chunk 15 was #1 of 15 by meaning (score 0.8793)
- Reranking ✅: kept: rank 1 of 4
- Context and token limits ✅: chunk handed over whole; 0 AI call(s) cut off by the token limit
- AI generation - specialist ✅: SOP Agent kept it: ", verify cannot start. - Safety requirements: - Never reach into the infeed or star wheel while the machine is running. - Never use"
- Knowledge graph ⚠: in the graph text, but NOT on the must-show warnings list: "Jam [source: FL-101-SOP Section 12.2] safety rule: Never reach into the infeed or the star wheel while the machine is running. Stop the ma"
- AI generation - writer ❌: had the fact and left it out of the report

### TC3 r3 - OQ:criticality-exact (Wrong severity rating)
Path: Knowledge graph ✅ → Knowledge graph ⚠ → Report rules (guardrail) ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (chose the rating) + Report rules (no floor for this fault)
- Knowledge graph ✅: matched fault: Product Supply Pressure Low (sure)
- Knowledge graph ⚠: the graph gives NO rating for this fault
- Report rules (guardrail) ⚠: no floor: the guardrail only enforces CRITICAL faults
- AI generation - writer ❌: rated MEDIUM, expected HIGH

### TC3 r3 - SR:safe-criticality-floor (Wrong severity rating)
Path: Knowledge graph ✅ → Knowledge graph ⚠ → Report rules (guardrail) ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (chose the rating) + Report rules (no floor for this fault)
- Knowledge graph ✅: matched fault: Product Supply Pressure Low (sure)
- Knowledge graph ⚠: the graph gives NO rating for this fault
- Report rules (guardrail) ⚠: no floor: the guardrail only enforces CRITICAL faults
- AI generation - writer ❌: rated MEDIUM, expected HIGH

### TC3 r3 - SR:safe-TC3-no-early-restart (Missing safety warning)
Fact: Do not restart the filler until the pressure is back to 1.5 to 2.0 bar.  
Path: Source documents ⚠ → Routing (supervisor) – → Knowledge graph ❌ → AI generation - writer –  
**Lost at: Source documents** · component: Source documents (only implied) + AI generation - writer
- Source documents ⚠: only implied, not written: FL-101-SOP Section 12.4 (Steps 4-5) - ONLY IMPLIED by the step order, never written as a prohibition
- Routing (supervisor) –: no document states the fact, nothing to search for
- Knowledge graph ❌: not in the graph text
- AI generation - writer –: never received the fact

### TC4 r3 - SR:safe-TC4-guards (Missing safety warning)
Fact: Do not open any guard until the machine has stopped and is locked out.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ✅ → Context and token limits ✅ → AI generation - specialist ✅ → Knowledge graph ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (dropped) + Knowledge graph (not on the must-show list)
- Source documents ✅: FL-101-SOP.txt: "- Stop the line at once with the emergency stop. Step 2 - Do not open any guard until the machine has stopped and is locked out"
- Routing (supervisor) ✅: the sop specialist searched SOP
- Chunking ✅: whole in chunk 16
- Embedding + vector search ✅: chunk 16 was #1 of 15 by meaning (score 0.8933)
- Reranking ✅: kept: rank 1 of 4
- Context and token limits ✅: chunk handed over whole; 0 AI call(s) cut off by the token limit
- AI generation - specialist ✅: SOP Agent kept it: ". Stop the line immediately with the emergency stop. 2. Do not open any guard until the machine has stopped and is locked out (Section 6."
- Knowledge graph ⚠: in the graph text, but NOT on the must-show warnings list: "steps: 1. Stop the line at once with the emergency stop. 2. Do not open any guard until the machine has stopped and is locked out. 3. Put eve"
- AI generation - writer ❌: had the fact and left it out of the report

### TC4 r3 - SR:safe-TC4-no-air (Missing safety warning)
Fact: Never use compressed air to clean up glass (air spreads glass).  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ✅ → Context and token limits ✅ → AI generation - specialist ✅ → Knowledge graph ⚠ → AI generation - writer ❌  
**Lost at: AI generation - writer** · component: AI generation - writer (dropped) + Knowledge graph (not on the must-show list)
- Source documents ✅: FL-101-SOP.txt: "ine is running. - Never reach past a guard. - Never use compressed air near open bottles or broken glass. - Keep the floor dry."
- Routing (supervisor) ✅: the sop specialist searched SOP
- Chunking ✅: whole in chunk 6, chunk 16, chunk 20
- Embedding + vector search ✅: chunk 16 was #1 of 15 by meaning (score 0.8933)
- Reranking ✅: kept: rank 1 of 4
- Context and token limits ✅: chunk handed over whole; 0 AI call(s) cut off by the token limit
- AI generation - specialist ✅: SOP Agent kept it: "Clean up with the red glass kit only - use a vacuum, never compressed air. 5. Rinse the filler with a sanitation rinse for 10 min"
- Knowledge graph ⚠: in the graph text, but NOT on the must-show warnings list: "Brittle Plastics Policy cleanup rule: Never use compressed air: air spreads glass steps: 1. Stop the line at o"
- AI generation - writer ❌: had the fact and left it out of the report

### TC5 r3 - TS:TC5-rinse (Missing step)
Fact: The 10-minute sanitation rinse must be done after the seal change, before normal production.  
Path: Source documents ✅ → Routing (supervisor) ✅ → Chunking ✅ → Embedding + vector search ✅ → Reranking ✅ → Context and token limits ✅ → AI generation - specialist ❌ → Knowledge graph ✅ → AI generation - writer ⚠  
**Lost at: Rubric / judge** · component: Rubric / judge: the words are there, please check the verdict
- Source documents ✅: FL-101-SOP.txt: "ntil the quality lead has checked it". Sanitation rinse A 10-minute rinse of the bowl, valves and nozzles with"; FL-101-Work-Instruction.txt: "Remove the lock and refill the bowl. Step 9 - SANITATION RINSE - MANDATORY Run the sanitation rinse for 10 minu"
- Routing (supervisor) ✅: the maintenance specialist searched Work Instruction
- Chunking ✅: whole in chunk 4
- Embedding + vector search ✅: chunk 4 was #5 of 8 by meaning (score 0.8588)
- Reranking ✅: kept: rank 3 of 4
- Context and token limits ✅: chunk handed over whole; 0 AI call(s) cut off by the token limit
- AI generation - specialist ❌: Maintenance Agent read it but left it out of its finding
- Knowledge graph ✅: in the graph text and on the must-show warnings list: "tion must not restart without it then required: Sanitation Rinse [source: WI-FL101-001 Step 9, FL-101-SOP Sections 4, 9, 12"
- AI generation - writer ⚠: the words ARE in the immediate actions: "hanged valve to confirm it is fully clicked in. Confirm the sanitation rinse has been completed. Step 3: Fix - If any bottle exceeds" - the judge still failed it
