# Search check — sections

Run 2026-10-06 13:09 by `evals/search_check.py` (free: Pinecone only). For each needed fact: did the app's real search hand the specialist a piece holding it? Labels: evals/search_labels.json.

| Set | Delivered to the specialist | In top 4 by meaning (app's wording) | In top 4 (operator's words only) | Cut apart (no single piece holds it) |
|---|---|---|---|---|
| teaching | 4/12 | 4/12 | 4/12 | 0 |
| fl101 | 17/21 | 17/21 | 17/21 | 0 |
| fresh | 11/19 | 11/19 | 11/19 | 0 |
| **All** | **32/52** | **32/52** | **32/52** | **0** |

## Every fact

| Question | Fact | Search | Delivered | Rank (app wording) | Rank (own words) | Note |
|---|---|---|---|---|---|---|
| T-1 | L1 a drip means a worn seal | sop | **no** | 5 | 5 |  |
| T-1 | L2 good bottle 495 to 505 ml | sop | **no** | 10 | 10 |  |
| T-1 | L4 weigh the first 20 bottles after the fix | maintenance | **no** | 11 | 11 |  |
| T-1 | L5 do not increase the fill time | sop | **no** | 5 | 5 |  |
| T-2 | L1 a drip means a worn seal | sop | yes | 1 | 1 |  |
| T-2 | L2 good bottle 495 to 505 ml | maintenance | **no** | 11 | 11 |  |
| T-2 | L4 weigh the first 20 bottles after the fix | maintenance | **no** | 11 | 11 |  |
| T-2 | L5 do not increase the fill time | sop | yes | 4 | 4 |  |
| T-3 | L1 a drip means a worn seal | sop | yes | 2 | 2 |  |
| T-3 | L2 good bottle 495 to 505 ml | maintenance | **no** | 7 | 7 |  |
| T-3 | L4 weigh the first 20 bottles after the fix | maintenance | **no** | 7 | 7 |  |
| T-3 | L5 do not increase the fill time | sop | yes | 2 | 2 |  |
| FL-01 | a drip means a worn seal | sop | yes | 1 | 1 |  |
| FL-01 | fill range 495 to 505 ml | sop | **no** | 9 | 9 |  |
| FL-01 | 3+ alarms in a shift = systemic fault | sop | yes | 1 | 1 |  |
| FL-01 | 10-minute sanitation rinse after the seal change | maintenance | **no** | 9 | 9 |  |
| FL-01 | weigh the first 20 bottles after the fix | maintenance | **no** | 9 | 9 |  |
| FL-02 | slight overfill after a seal change is expected | maintenance | yes | 1 | 1 |  |
| FL-02 | do not change any settings | maintenance | yes | 1 | 1 |  |
| FL-02 | 10-minute sanitation rinse | maintenance | yes | 3 | 3 |  |
| FL-02 | first 20 bottles within 495 to 505 ml | maintenance | yes | 3 | 3 |  |
| FL-03 | check the guide rail position matches the bottle size | sop | yes | 2 | 2 |  |
| FL-03 | rails to position B for 330 ml | sop | yes | 1 | 1 |  |
| FL-03 | restart at 60 per minute for 2 minutes | sop | yes | 2 | 2 |  |
| FL-03 | never clear a jam while running | sop | **no** | 14 | 14 |  |
| FL-04 | emergency stop at once | sop | yes | 1 | 1 |  |
| FL-04 | hold bottles from the last 30 minutes | sop | yes | 1 | 1 |  |
| FL-04 | vacuum, never compressed air | sop | yes | 1 | 1 |  |
| FL-04 | quality lead signs off before restart | sop | yes | 1 | 1 |  |
| FL-05 | clean the supply filter | sop | yes | 1 | 1 |  |
| FL-05 | bleed air from the supply line | sop | yes | 1 | 1 |  |
| FL-05 | pressure back to 1.5 to 2.0 bar | sop | yes | 1 | 1 |  |
| FL-05 | weigh the first 20 bottles after restart | sop | yes | 1 | 1 |  |
| FR-01 | checkweigher test bottles 490 / 500 / 510 ml | sop | **no** | 20 | 20 |  |
| FR-01 | sanitation rinse if stopped more than 4 hours | sop | **no** | 13 | 13 |  |
| FR-01 | start at 60 bottles per minute | sop | **no** | 13 | 13 |  |
| FR-01 | weigh the first 20 bottles, 495 to 505 ml | sop | **no** | 13 | 13 |  |
| FR-01 | then 120 bottles per minute | sop | **no** | 13 | 13 |  |
| FR-02 | no drip = blocked nozzle | sop | yes | 2 | 2 |  |
| FR-02 | lock out and clean the nozzle | sop | yes | 2 | 2 |  |
| FR-02 | check the product supply pressure | sop | yes | 2 | 2 |  |
| FR-03 | more than 1 in 100 over an hour: tell the shift lead | sop | yes | 2 | 2 |  |
| FR-03 | rising reject count = first sign of worn seals | sop | yes | 2 | 2 |  |
| FR-03 | look at the fill valves for dripping | sop | yes | 2 | 2 |  |
| FR-04 | rails to position B (330 ml) and lock them | sop | yes | 1 | 1 |  |
| FR-04 | fit the matching star wheel | sop | yes | 1 | 1 |  |
| FR-04 | run 20 bottles at 60 per minute | sop | yes | 1 | 1 |  |
| FR-04 | record the changeover; shift lead signs | sop | yes | 1 | 1 |  |
| FR-05 | leak at the valve body: fit a new O-ring | maintenance | yes | 1 | 1 |  |
| FR-05 | trained maintenance technicians only | maintenance | **no** | 12 | 12 |  |
| FR-05 | seal kit SEAL-FV-24 (seal and O-ring) | maintenance | **no** | 5 | 5 |  |
| FR-05 | food-grade lubricant only | maintenance | **no** | 13 | 13 |  |

How to read it: 'delivered' is what the specialist actually saw. A fact that is in one piece but ranks below 4 is a RANKING problem; a fact no single piece holds is a CUTTING problem (section chunking fixes that).