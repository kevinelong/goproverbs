use goproverbs::engine::{Weights, rank_moves};
use goproverbs::search::{Limits, Mode, analyze, evaluate};
use goproverbs::{BoardSize, Color, Game, Move, Phase};

fn game(n: u8) -> Game {
    Game::with_rules(
        BoardSize::new(n).unwrap(),
        0.5,
        goproverbs::Rules::TrompTaylor,
    )
    .unwrap()
}
fn action(g: &Game, s: &str) -> Move {
    Move::from_gtp(s, g.board().size()).unwrap()
}
fn budget(mode: Mode, depth: u8) -> Limits {
    Limits {
        mode,
        max_depth: depth,
        max_nodes: 200_000,
        time_ms: 10_000,
        ..Limits::default()
    }
}
// Independent exhaustive recursion: no Reader, pruning, iteration, or beam selection.
fn oracle(g: &Game, w: &Weights, depth: u8) -> f64 {
    if depth == 0 || g.phase() == Phase::Finished {
        return evaluate(g, g.to_play(), w);
    }
    rank_moves(g, g.to_play(), w)
        .iter()
        .map(|candidate| {
            let mut next = g.clone();
            next.play(candidate.action).unwrap();
            0.15 * candidate.score.clamp(-20.0, 20.0) - oracle(&next, w, depth - 1)
        })
        .fold(f64::NEG_INFINITY, f64::max)
}

#[test]
fn full_width_alpha_beta_and_minimax_match_exhaustive_oracle() {
    for moves in [vec![], vec!["B2"], vec!["A1", "C3"], vec!["B2", "A2", "B1"]] {
        let mut g = game(3);
        for m in moves {
            g.play(action(&g, m)).unwrap();
        }
        let before = g.clone();
        let w = Weights::default();
        let expected = oracle(&g, &w, 3);
        let full = analyze(&g, g.to_play(), &w, budget(Mode::Full, 3)).unwrap();
        let plain = analyze(&g, g.to_play(), &w, budget(Mode::Minimax, 3)).unwrap();
        assert_eq!((full.depth, plain.depth), (3, 3));
        assert!(!full.limited && !plain.limited);
        assert!((expected - full.score).abs() < 1e-10);
        assert!((expected - plain.score).abs() < 1e-10);
        assert_eq!(full.action, plain.action);
        assert!(full.nodes <= plain.nodes);
        assert_eq!(g, before);
    }
}

#[test]
fn hybrid_can_refute_the_heuristic_favorite_and_explain_its_decision() {
    let mut g = game(5);
    for s in [
        "C3", "B2", "B1", "A2", "E1", "C4", "E4", "B5", "E5", "D5", "E3", "D1", "A5", "A3", "D2",
        "A1", "B3", "D3", "B4", "C5", "D4", "C2",
    ] {
        g.play(action(&g, s)).unwrap();
    }
    let w = Weights::default();
    let greedy = rank_moves(&g, g.to_play(), &w)[0].action;
    assert_eq!(greedy, action(&g, "C1"));
    let before = g.clone();
    let a = analyze(&g, g.to_play(), &w, budget(Mode::Hybrid, 3)).unwrap();
    assert_eq!(a.depth, 3);
    assert_ne!(a.action, greedy);
    assert_eq!(g, before);
    let favorite = a.root_evidence.iter().find(|e| e.action == greedy).unwrap();
    let chosen = a
        .root_evidence
        .iter()
        .find(|e| e.action == a.action)
        .unwrap();
    assert!(favorite.nominated && chosen.nominated);
    assert_eq!((favorite.depth, chosen.depth), (3, 3));
    assert!(chosen.verified.unwrap() > favorite.verified.unwrap());
    assert!((chosen.verified.unwrap() - a.score).abs() < 1e-10);
    for m in a.principal_variation {
        g.play(m).unwrap();
    }
}

#[test]
fn incomplete_hybrid_round_never_leaks_mixed_depth_scores() {
    let g = game(5);
    let w = Weights::default();
    let count = rank_moves(&g, g.to_play(), &w).len();
    let a = analyze(
        &g,
        g.to_play(),
        &w,
        Limits {
            max_nodes: count + 1,
            ..budget(Mode::Hybrid, 3)
        },
    )
    .unwrap();
    assert_eq!(a.depth, 1);
    assert!(a.limited && a.nodes <= count + 1);
    assert!(
        a.root_evidence
            .iter()
            .all(|e| e.scout.is_some() && e.verified.is_none() && e.depth == 0)
    );
    for mode in [Mode::Selective, Mode::Full, Mode::Minimax, Mode::Hybrid] {
        let zero = analyze(
            &g,
            g.to_play(),
            &w,
            Limits {
                time_ms: 0,
                ..budget(mode, 3)
            },
        )
        .unwrap();
        assert_eq!(zero.depth, 0);
        assert!(g.clone().play(zero.action).is_ok());
    }
}

#[test]
fn full_and_minimax_ignore_quiet_beam_and_validate_mode_controls() {
    let g = game(3);
    for mode in [Mode::Full, Mode::Minimax] {
        let narrow = analyze(
            &g,
            g.to_play(),
            &Weights::default(),
            Limits {
                beam: 1,
                ..budget(mode, 3)
            },
        )
        .unwrap();
        let wide = analyze(
            &g,
            g.to_play(),
            &Weights::default(),
            Limits {
                beam: 625,
                ..budget(mode, 3)
            },
        )
        .unwrap();
        assert_eq!(
            (narrow.action, narrow.score, narrow.nodes),
            (wide.action, wide.score, wide.nodes)
        );
    }
    assert!("guess".parse::<Mode>().is_err());
    assert!(
        Limits {
            shortlist: 0,
            ..Limits::default()
        }
        .validate()
        .is_err()
    );
}

#[test]
fn whole_board_opening_proxies_are_gated_to_19_but_local_rescue_transfers() {
    for n in [5, 9, 13, 19, 25] {
        let mut g = game(n);
        let ranked = rank_moves(&g, Color::Black, &Weights::default());
        let has_opening = ranked.iter().any(|c| {
            c.contributions
                .iter()
                .any(|t| matches!(t.feature, "empty_corner" | "side_development" | "early_33"))
        });
        assert_eq!(has_opening, n == 19);
        g.play_as(Color::Black, action(&g, "B2")).unwrap();
        for s in ["A2", "C2", "B1"] {
            g.play_as(Color::White, action(&g, s)).unwrap();
        }
        let ranked = rank_moves(&g, Color::Black, &Weights::default());
        let rescue = ranked
            .iter()
            .find(|c| c.action == action(&g, "B3"))
            .unwrap();
        assert!(
            rescue
                .contributions
                .iter()
                .any(|t| t.feature == "save_atari" && t.value == 0.25)
        );
    }
}
