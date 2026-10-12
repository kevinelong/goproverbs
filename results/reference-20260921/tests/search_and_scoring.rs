use goproverbs::engine::Weights;
use goproverbs::search::{Limits, analyze, evaluate};
use goproverbs::{BoardSize, Color, Error, Game, Move, Phase, Point, Rules};
fn tt(n: u8) -> Game {
    Game::with_rules(BoardSize::new(n).unwrap(), 0.5, Rules::TrompTaylor).unwrap()
}
fn mv(g: &Game, s: &str) -> Move {
    Move::from_gtp(s, g.board().size()).unwrap()
}
fn put(g: &mut Game, color: Color, s: &str) {
    g.play_as(color, mv(g, s)).unwrap();
}
fn limits(depth: u8) -> Limits {
    Limits {
        time_ms: 10_000,
        max_nodes: 50_000,
        max_depth: depth,
        beam: 6,
        tactical_plies: 0,
        ..Limits::default()
    }
}

#[test]
fn area_neutral_komi_and_two_pass_finish() {
    let mut g = tt(3);
    let score = g.board().area_score(g.komi());
    assert_eq!((score.black, score.white, score.neutral), (0, 0, 9));
    put(&mut g, Color::Black, "A1");
    put(&mut g, Color::White, "C3");
    let score = g.board().area_score(g.komi());
    assert_eq!((score.black, score.white, score.neutral), (1, 1, 7));
    assert!(g.final_result().is_none());
    g.play(Move::Pass).unwrap();
    assert_eq!(g.phase(), Phase::Playing);
    g.play(Move::Pass).unwrap();
    assert_eq!(g.phase(), Phase::Finished);
    assert_eq!(g.final_result().as_deref(), Some("W+0.5"));
    assert!(g.to_sgf().contains("RU[Tromp-Taylor]RE[W+0.5]"));
    assert!(g.play(Move::Pass).is_err());
}
#[test]
fn enclosed_empty_area_belongs_to_one_color() {
    let mut g = tt(3);
    for s in ["B1", "B2", "B3"] {
        put(&mut g, Color::Black, s);
    }
    put(&mut g, Color::White, "C2");
    let score = g.board().area_score(0.0);
    assert_eq!((score.black, score.white, score.neutral), (6, 1, 2));
}
#[test]
fn multi_stone_suicide_and_superko_are_distinct() {
    let mut g = tt(5);
    for s in ["A1", "B1"] {
        put(&mut g, Color::Black, s);
    }
    for s in ["A2", "C1", "C2", "B3"] {
        put(&mut g, Color::White, s);
    }
    assert_eq!(g.play_as(Color::Black, mv(&g, "B2")), Ok(0));
    for s in ["A1", "B1", "B2"] {
        assert_eq!(
            g.board().at(Point::from_gtp(s, g.board().size()).unwrap()),
            Ok(None)
        );
    }
    assert_eq!(g.captures_by(Color::White), 3);
    // B2 still reaches empty B1, so use a separate fully surrounded point.
    let mut surrounded = tt(3);
    for s in ["A2", "B1"] {
        put(&mut surrounded, Color::White, s);
    }
    let before = surrounded.clone();
    assert_eq!(
        surrounded.play_as(Color::Black, mv(&surrounded, "A1")),
        Err(Error::Ko)
    );
    assert_eq!(surrounded, before);
}
#[test]
fn superko_remembers_before_pass_and_turn_changes() {
    let mut g = tt(5);
    for s in ["A2", "B1", "C2"] {
        put(&mut g, Color::Black, s);
    }
    for s in ["B2", "A3", "C3", "B4"] {
        put(&mut g, Color::White, s);
    }
    put(&mut g, Color::Black, "B3");
    g.play(Move::Pass).unwrap();
    assert_eq!(g.play_as(Color::White, mv(&g, "B2")), Err(Error::Ko));
}
#[test]
fn search_reads_legal_line_and_preserves_input() {
    let mut g = tt(5);
    put(&mut g, Color::Black, "B2");
    for s in ["A2", "C2", "B1"] {
        put(&mut g, Color::White, s);
    }
    let before = g.clone();
    let a = analyze(&g, Color::Black, &Weights::default(), limits(3)).unwrap();
    assert_eq!(a.depth, 3);
    assert_eq!(a.action, mv(&g, "B3"));
    assert_eq!(g, before);
    for action in a.principal_variation {
        g.play(action).unwrap();
    }
}
#[test]
fn zero_time_and_node_limits_return_legal_fallbacks() {
    let g = tt(9);
    for budget in [
        Limits {
            time_ms: 0,
            ..limits(4)
        },
        Limits {
            max_nodes: 1,
            ..limits(4)
        },
    ] {
        let a = analyze(&g, Color::Black, &Weights::default(), budget).unwrap();
        assert_eq!(a.depth, 0);
        assert!(a.limited);
        assert!(a.nodes <= budget.max_nodes);
        assert!(g.clone().play(a.action).is_ok());
    }
}
#[test]
fn deterministic_search_and_antisymmetric_evaluation() {
    let mut g = tt(3);
    put(&mut g, Color::Black, "B2");
    let w = Weights::default();
    assert!((evaluate(&g, Color::Black, &w) + evaluate(&g, Color::White, &w)).abs() < 1e-10);
    let a = analyze(&g, Color::White, &w, limits(2)).unwrap();
    let b = analyze(&g, Color::White, &w, limits(2)).unwrap();
    assert_eq!(
        (a.action, a.score, a.depth, a.nodes),
        (b.action, b.score, b.depth, b.nodes)
    );
}
#[test]
fn weight_profiles_round_trip_and_reject_bad_entries() {
    let mut w = Weights::default();
    w.set("capture", 3.25).unwrap();
    assert_eq!(
        Weights::from_text(&w.to_text()).unwrap().to_text(),
        w.to_text()
    );
    for t in [
        "capture=1\ncapture=2",
        "typo=1",
        "capture=NaN",
        "capture=inf",
        "capture=1001",
        "capture 1",
    ] {
        assert!(Weights::from_text(t).is_err(), "{t}");
    }
}

#[test]
fn search_avoids_a_larger_snapback_recapture() {
    let mut g = tt(5);
    for s in [
        "C3", "B2", "B1", "A2", "E1", "C4", "E4", "B5", "E5", "D5", "E3", "D1", "A5", "A3", "D2",
        "A1", "B3", "D3", "B4", "C5", "D4", "C2",
    ] {
        g.play(mv(&g, s)).unwrap();
    }
    let weights = Weights::default();
    let greedy = goproverbs::engine::rank_moves(&g, Color::Black, &weights)[0].action;
    assert_eq!(greedy, mv(&g, "C1"));
    let mut trap = g.clone();
    let gain = trap.play(greedy).unwrap();
    let loss = trap.play(mv(&trap, "D1")).unwrap();
    assert!(loss > gain);
    let a = analyze(
        &g,
        Color::Black,
        &weights,
        Limits {
            beam: 12,
            ..limits(2)
        },
    )
    .unwrap();
    assert_eq!(a.depth, 2);
    assert_ne!(a.action, greedy);
}

#[test]
fn atari_rescue_features_are_invariant_under_all_board_symmetries() {
    let n = BoardSize::new(9).unwrap();
    let original = ["B2", "A2", "C2", "B1"];
    for mirror in [false, true] {
        for rotations in 0..4 {
            let transform = |s: &str| {
                let p = Point::from_gtp(s, n).unwrap();
                let (mut x, mut y) = (p.col(), p.row());
                if mirror {
                    x = 8 - x;
                }
                for _ in 0..rotations {
                    (x, y) = (8 - y, x);
                }
                Point::new(x, y, n).unwrap()
            };
            let mut g = tt(9);
            for (i, s) in original.iter().enumerate() {
                g.play_as(
                    if i == 0 { Color::Black } else { Color::White },
                    Move::Play(transform(s)),
                )
                .unwrap();
            }
            let ranked = goproverbs::engine::rank_moves(&g, Color::Black, &Weights::default());
            let rescue = ranked
                .iter()
                .find(|c| c.action == Move::Play(transform("B3")))
                .unwrap();
            assert!(
                rescue
                    .contributions
                    .iter()
                    .any(|t| t.feature == "save_atari" && t.value == 0.25)
            );
            assert_eq!(ranked[0].action, rescue.action);
        }
    }
}

#[test]
fn tactical_extensions_share_budgets_and_return_legal_bounded_lines() {
    let mut g = tt(5);
    put(&mut g, Color::Black, "B2");
    for s in ["A2", "C2", "B1"] {
        put(&mut g, Color::White, s);
    }
    let before = g.clone();
    let budget = Limits {
        tactical_plies: 2,
        max_nodes: 5000,
        ..limits(1)
    };
    let a = analyze(&g, Color::Black, &Weights::default(), budget).unwrap();
    assert_eq!(g, before);
    assert_eq!(a.depth, 1);
    assert!(a.tactical_nodes > 0);
    assert!(a.tactical_nodes <= a.nodes && a.nodes <= budget.max_nodes);
    assert!(a.principal_variation.len() <= usize::from(a.depth + budget.tactical_plies));
    for action in &a.principal_variation {
        g.play(*action).unwrap();
    }
    let leaf = a.leaf_terms.iter().map(|t| t.score).sum::<f64>();
    assert!((leaf + a.path_preference - a.score).abs() < 1e-10);
    let tiny = analyze(
        &before,
        Color::Black,
        &Weights::default(),
        Limits {
            max_nodes: 1,
            ..budget
        },
    )
    .unwrap();
    assert_eq!(tiny.depth, 0);
    assert!(tiny.limited && tiny.nodes <= 1);
}

#[test]
fn quiet_leaves_do_not_extend_and_invalid_extension_limits_fail() {
    let g = tt(9);
    let a = analyze(
        &g,
        Color::Black,
        &Weights::default(),
        Limits {
            tactical_plies: 4,
            ..limits(1)
        },
    )
    .unwrap();
    assert_eq!(a.depth, 1);
    assert_eq!(a.tactical_nodes, 0);
    assert_eq!(a.principal_variation.len(), 1);
    assert!(
        Limits {
            tactical_plies: 5,
            ..limits(1)
        }
        .validate()
        .is_err()
    );
}
