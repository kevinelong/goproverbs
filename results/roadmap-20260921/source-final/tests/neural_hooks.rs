use goproverbs::engine::Weights;
use goproverbs::search::{self, LeafEvaluator, Limits, Mode};
use goproverbs::{BoardSize, Color, Game, Move, Rules};
use std::time::Instant;

fn game() -> Game {
    Game::with_rules(BoardSize::new(5).unwrap(), 0.5, Rules::TrompTaylor).unwrap()
}
fn limits() -> Limits {
    Limits {
        mode: Mode::Hybrid,
        time_ms: 10000,
        max_nodes: 100000,
        max_depth: 2,
        shortlist: 1,
        beam: 2,
        ..Limits::default()
    }
}
struct ExactHeuristic;
impl LeafEvaluator for ExactHeuristic {
    fn evaluate(&mut self, g: &Game, _: Instant) -> Option<f64> {
        Some(search::evaluate(g, g.to_play(), &Weights::default()))
    }
}
struct Failure;
impl LeafEvaluator for Failure {
    fn evaluate(&mut self, _: &Game, _: Instant) -> Option<f64> {
        None
    }
}

#[test]
fn empty_guidance_and_equivalent_leaf_preserve_completed_answers() {
    let g = game();
    let w = Weights::default();
    let a = search::analyze(&g, Color::Black, &w, limits()).unwrap();
    let b = search::analyze_guided(&g, Color::Black, &w, limits(), &[], None).unwrap();
    let c = search::analyze_guided(
        &g,
        Color::Black,
        &w,
        limits(),
        &[],
        Some(&mut ExactHeuristic),
    )
    .unwrap();
    assert_eq!((a.action, a.score, a.depth), (b.action, b.score, b.depth));
    assert_eq!((a.action, a.score, a.depth), (c.action, c.score, c.depth));
    assert!(c.external_leaf && c.leaf_calls > 0);
    assert!(c.leaf_terms.is_empty());
}

#[test]
fn neural_nominees_are_added_once_without_mutating_game() {
    let g = game();
    let before = g.clone();
    let w = Weights::default();
    let hint = Move::from_gtp("E5", g.board().size()).unwrap();
    let a = search::analyze_guided(&g, Color::Black, &w, limits(), &[hint, hint], None).unwrap();
    assert_eq!(g, before);
    let evidence: Vec<_> = a
        .root_evidence
        .iter()
        .filter(|e| e.action == hint)
        .collect();
    assert_eq!(evidence.len(), 1);
    assert!(evidence[0].neural_hint && evidence[0].nominated);
    assert_eq!(evidence[0].depth, 2);
}

#[test]
fn failed_evaluation_retains_only_complete_heuristic_scout() {
    let g = game();
    let w = Weights::default();
    let a =
        search::analyze_guided(&g, Color::Black, &w, limits(), &[], Some(&mut Failure)).unwrap();
    assert_eq!(a.depth, 1);
    assert!(a.limited && !a.external_leaf);
    assert!(a.root_evidence.iter().all(|e| e.verified.is_none()));
    assert!(g.clone().play(a.action).is_ok());
}

#[test]
fn invalid_guidance_fails_without_changing_game() {
    let mut g = game();
    let hint = Move::from_gtp("C3", g.board().size()).unwrap();
    g.play(hint).unwrap();
    let before = g.clone();
    assert!(
        search::analyze_guided(
            &g,
            Color::White,
            &Weights::default(),
            limits(),
            &[hint],
            None
        )
        .is_err()
    );
    assert_eq!(g, before);
    assert!(
        search::analyze_guided(
            &g,
            Color::White,
            &Weights::default(),
            Limits::default(),
            &[],
            Some(&mut ExactHeuristic)
        )
        .is_err()
    );
}

#[test]
fn complete_learned_one_ply_round_survives_interrupted_deeper_round() {
    struct Counted {
        left: usize,
    }
    impl LeafEvaluator for Counted {
        fn evaluate(&mut self, _: &Game, _: Instant) -> Option<f64> {
            if self.left == 0 {
                return None;
            }
            self.left -= 1;
            Some(7.0)
        }
    }
    let g = game();
    let w = Weights::default();
    let scout = search::analyze(
        &g,
        Color::Black,
        &w,
        Limits {
            max_depth: 1,
            ..limits()
        },
    )
    .unwrap();
    let count = scout.root_evidence.iter().filter(|e| e.nominated).count();
    let a = search::analyze_guided(
        &g,
        Color::Black,
        &w,
        limits(),
        &[],
        Some(&mut Counted { left: count }),
    )
    .unwrap();
    assert_eq!(a.depth, 1);
    assert!(a.external_leaf && a.limited);
    assert!(
        a.root_evidence
            .iter()
            .filter(|e| e.nominated)
            .all(|e| e.depth == 1 && e.verified.is_some())
    );
}
