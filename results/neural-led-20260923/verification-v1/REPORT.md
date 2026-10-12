# Small-search verification experiment

Status: complete
Phase: development; profiles: 60; reference cases: 40.

Same-model reference estimates; internal samples from previously inspected games.
No game-strength claim. Validation runs only after development passes.

Timing gate:
```json
{
  "selected_visits": 16,
  "budgets": {
    "4": {
      "decisions": 20,
      "median_ms": 49.15089998394251,
      "p95_ms": 69.99499991070479,
      "max_ms": 75.75249997898936,
      "verified": {
        "neural": 10,
        "combined": 10
      },
      "passed": true
    },
    "8": {
      "decisions": 20,
      "median_ms": 56.53795006219298,
      "p95_ms": 80.78259998001158,
      "max_ms": 83.29300000332296,
      "verified": {
        "neural": 10,
        "combined": 10
      },
      "passed": true
    },
    "16": {
      "decisions": 20,
      "median_ms": 74.8299999977462,
      "p95_ms": 100.80159991048276,
      "max_ms": 102.07499994430691,
      "verified": {
        "neural": 10,
        "combined": 10
      },
      "passed": true
    }
  }
}
```

development gate:
```json
{
  "passed": false,
  "cases": 40,
  "openings": 20,
  "role_counts": {
    "neural": 20,
    "combined": 20
  },
  "opening_means": {
    "128": {
      "versus_current": 0.005846617162241003,
      "versus_policy": 0.006853449585000002
    },
    "512": {
      "versus_current": 0.007007008998160007,
      "versus_policy": 0.006772203112500002
    }
  },
  "role_means": {
    "neural": {
      "128": 0.011439721463412007,
      "512": 0.014387276203805019
    },
    "combined": {
      "128": 0.00025351286106999906,
      "512": -0.0003732582074850033
    }
  },
  "beneficial": 6,
  "harmful": 2,
  "severe_harm": 0,
  "p95_ms": 102.13500005193055,
  "max_ms": 106.35979997459799
}
```

development gate failed; remaining validation/fresh games held.

