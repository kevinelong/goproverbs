# Saved disagreement review

Status: complete; completed 79/79 cases.
Deeper same-model estimates are not ground truth. Enriched sample, paired openings.

| Stratum | Visits | Cases | Chosen better | Chosen worse | Near tie | Mean winrate difference | Mean score difference |
|---|---:|---:|---:|---:|---:|---:|---:|
| confidence | 128 | 39 | 9 | 15 | 15 | -0.009011950206761536 | -3.128000094976923 |
| confidence | 512 | 39 | 10 | 15 | 14 | -0.007576160141865126 | -3.3377581557000005 |
| specialist | 128 | 40 | 5 | 4 | 31 | 0.0033503516427899984 | -3.777271839749999 |
| specialist | 512 | 40 | 5 | 4 | 31 | 0.0023603736869025013 | -3.8817020014999994 |

Confidence: chosen versus root policy. Specialist: chosen versus best saved neural candidate.
Better/worse requires at least0.001 estimated win-probability difference.
Means above are descriptive case averages, not independent-game statistics.

Development candidate gate: {"beneficial": 8, "cases": 19, "harmful": 4, "opening_mean_improvement": {"128": 0.0019178969806999896, "512": -0.0023485219209500034}, "openings": 10, "passed": false, "severe_harm": 0}
Validation candidate gate: {"beneficial": 7, "cases": 20, "harmful": 6, "opening_mean_improvement": {"128": 0.015672849722485005, "512": 0.017139425797587}, "openings": 10, "passed": false, "severe_harm": 0}
Implement candidate: False
Validation is not counted as support unless development passes. No threshold tuning or pooled strength claim.
confidence: depth-direction reversals=3; saturated pairs at512 visits=9.
specialist: depth-direction reversals=0; saturated pairs at512 visits=27.
