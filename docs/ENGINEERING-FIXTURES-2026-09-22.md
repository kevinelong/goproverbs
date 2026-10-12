# Composed shape and scoring regressions

These are engineering cases, not expert-reviewed best-move labels or a fresh
playing-strength holdout. They never tune weights or change defaults.

`tests/engineering_shapes.rs` checks three specific properties:

- On a 2x2 diagonal-stone position, both empty intersections are neutral; each
  player's invasion at either point has an immediate two-stone capture reply.
  Two passes score a draw at zero komi. This is a finite mutual-liberty example,
  not general seki or life/death adjudication.
- Connecting two separate strings has a connection contribution; filling a
  gap in a string already joined around the back does not.
- Filling an unambiguous owned point exchanges territory for a stone without
  gaining an extra Tromp-Taylor area point.

Native SGF regressions separately cover exact ko history, passes, move limits,
and atomic import failure. Existing snapback and symmetry regressions remain.
Broader ladders, ko threats, strategic shape exceptions, and expert-labeled
19x19 endgames still require stronger independent evidence.
