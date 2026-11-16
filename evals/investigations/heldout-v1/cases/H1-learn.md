# H1: The scale test failed before start-up

Full evidence: [H1.md](H1.md)

> **Remember this:** PlantMind treats every question as a broken machine, so it invented a repair job nobody needed.

### How PlantMind works (the same on every page)

```
Question → ① Search → ② Helpers → ③ Problem picker → ④ Writer → Answer → ⑤ Checker
           finds       summarise    picks which of     writes using
           document    what they    5 known machine    a fixed form
           pages       found        problems it is     (lock, find, fix, check)
```

### 1. What happened in the plant
Before starting the line, the operator tests the scale that weighs every bottle. A too-heavy test bottle went through when the scale should have rejected it. **The scale failed its test.**

The operator asked: *"Can I start the line and just weigh bottles by hand until someone comes to look at it?"*

### 2. PlantMind's answer (shortened, original words)

> **HOW CRITICAL IS IT:** HIGH. *"The SOP requires an immediate line stop and LOTO for any checkweigher failure."*
>
> **Do NOT:** start the machine · weigh bottles by hand · change the fill time · clear a jam while running · reach past a guard · use compressed air near broken glass · remove a lock you didn't place · restart until the First-Bottle Check is signed off by the shift supervisor
>
> **Step 1:** lock out the machine and isolate the checkweigher.
> **Step 2:** *"inspect the checkweigher sensor and calibration settings; verify wiring"*
> **Step 3:** *"recalibrate or repair the checkweigher as required"*
> **Step 4:** repeat the 490 / 500 / 510 ml test.
> **Step 5:** place the line on QA HOLD; notify the quality lead.
>
> **Report confidence:** *"HIGH… Engineer review: not needed"*

### 3. The right answer (from the SOP)
- Don't start.
- Call the quality lead.
- Write it on the start-up checklist; the shift lead signs it.

### 4. Where it broke

| What went wrong | Where | Why (with PlantMind's own words) |
|---|---|---|
| Made-up repair steps | **③ + ④** | ③ guessed this was an "Overfill" machine fault. ④'s form always asks "find the fault, fix it", so it wrote **"verify wiring… recalibrate or repair the checkweigher"**. No document says this, and the SOP says operators must not do electrical repairs. |
| Rules about other problems | **③** | Because ③ picked "Overfill", all of Overfill's rules were copied in: **"Do NOT clear a jam… use compressed air near broken glass… change the fill time"**. None apply to a scale test. |
| Forgot the checklist and sign-off | **②** | Search found *"Record every check on the pre-start checklist. The shift lead signs it."* A helper left it out of its summary, so the answer says instead: **"signed off by the shift supervisor"** for a different check. |
| Rated HIGH (should be MEDIUM) | **④** | The writer invented a rule to justify it: **"The SOP requires an immediate line stop and LOTO for any checkweigher failure."** The SOP says no such thing. |
| Said it was sure | **③** | The "Overfill" pick was almost a coin toss, yet the answer says **"HIGH… Engineer review: not needed"**. |
| Unsafe steps passed | **⑤** | The checker judged **"verify wiring… recalibrate"** as *"safe and compliant"*. |

**What went right:** "Don't start" and "call the quality lead" were correct.
