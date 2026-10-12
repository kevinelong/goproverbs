use goproverbs::engine::{Weights, rank_moves};
use goproverbs::{BoardSize, Color, Error, Game, Move, Phase, Point};

fn game(size: u8) -> Game {
    Game::new(BoardSize::new(size).unwrap(), 6.5).unwrap()
}
fn mv(g: &Game, text: &str) -> Move {
    Move::from_gtp(text, g.board().size()).unwrap()
}
fn point(g: &Game, text: &str) -> Point {
    Point::from_gtp(text, g.board().size()).unwrap()
}
fn put(g: &mut Game, color: Color, text: &str) {
    g.play_as(color, mv(g, text)).unwrap();
}

#[test]
fn all_coordinates_round_trip_and_orient_correctly() {
    for n in 2..=25 {
        let size = BoardSize::new(n).unwrap();
        for row in 0..n {
            for col in 0..n {
                let p = Point::new(col, row, size).unwrap();
                assert_eq!(
                    Point::from_gtp(&p.to_gtp(size).unwrap().to_lowercase(), size),
                    Ok(p)
                );
                assert_eq!(Point::from_sgf(&p.to_sgf(size).unwrap(), size), Ok(p));
            }
        }
    }
    let size = BoardSize::default();
    assert_eq!(
        Point::from_gtp("A19", size).unwrap().to_sgf(size).unwrap(),
        "aa"
    );
    assert_eq!(
        Point::from_gtp("T1", size).unwrap().to_sgf(size).unwrap(),
        "ss"
    );
    assert_eq!(Point::from_gtp("J10", size).unwrap().col(), 8);
}

#[test]
fn bad_coordinates_and_cross_board_points_are_rejected() {
    let size = BoardSize::new(9).unwrap();
    for text in [
        "", "I4", "A0", "A10", "T1", "D-1", "D+1", "D4x", "D 4", "\u{e9}1",
    ] {
        assert!(Point::from_gtp(text, size).is_err(), "{text}");
    }
    let mut g = game(9);
    let before = g.clone();
    assert_eq!(
        g.play(Move::Play(
            Point::new(18, 18, BoardSize::default()).unwrap()
        )),
        Err(Error::OutOfBounds)
    );
    assert_eq!(g, before);
    assert!(BoardSize::new(1).is_err());
    assert!(BoardSize::new(26).is_err());
    assert!(Game::new(size, f64::NAN).is_err());
}

#[test]
fn sgf_pass_legacy_tt_is_not_confused_with_large_board_point() {
    assert_eq!(Move::from_sgf("", BoardSize::default()), Ok(Move::Pass));
    assert_eq!(Move::from_sgf("tt", BoardSize::default()), Ok(Move::Pass));
    assert!(matches!(
        Move::from_sgf("tt", BoardSize::new(25).unwrap()),
        Ok(Move::Play(_))
    ));
}

#[test]
fn illegal_move_does_not_change_turn_board_or_history() {
    let mut g = game(9);
    g.play(mv(&g, "D4")).unwrap();
    assert_eq!(g.to_play(), Color::White);
    let before = g.clone();
    assert_eq!(g.play(mv(&g, "D4")), Err(Error::Occupied));
    assert_eq!(g, before);
    assert_eq!(g.play_as(Color::Black, mv(&g, "D4")), Err(Error::Occupied));
    assert_eq!(g, before);
}

#[test]
fn groups_are_orthogonal_and_liberties_unique() {
    let mut g = game(5);
    for p in ["A2", "B1", "B2", "C3"] {
        put(&mut g, Color::Black, p);
    }
    let group = g.board().group_at(point(&g, "B2")).unwrap().unwrap();
    assert_eq!(group.stones.len(), 3);
    assert_eq!(group.liberties.len(), 5);
    assert_eq!(
        g.board()
            .group_at(point(&g, "C3"))
            .unwrap()
            .unwrap()
            .stones
            .len(),
        1
    );
}

#[test]
fn capture_multiple_groups_before_checking_self_capture() {
    let mut g = game(3);
    for p in ["A2", "C2", "B3"] {
        put(&mut g, Color::Black, p);
    }
    for p in ["A1", "C1", "B2"] {
        put(&mut g, Color::White, p);
    }
    assert_eq!(g.play_as(Color::Black, mv(&g, "B1")), Ok(3));
    assert_eq!(g.captures_by(Color::Black), 3);
    for p in ["A1", "C1", "B2"] {
        assert_eq!(g.board().at(point(&g, p)), Ok(None));
    }
}

#[test]
fn whole_connected_string_is_captured_once() {
    let mut g = game(5);
    for p in ["B2", "C2"] {
        put(&mut g, Color::White, p);
    }
    for p in ["A2", "B1", "C1", "D2", "B3"] {
        put(&mut g, Color::Black, p);
    }
    assert_eq!(g.play_as(Color::Black, mv(&g, "C3")), Ok(2));
    assert_eq!(g.captures_by(Color::Black), 2);
}

#[test]
fn suicide_is_atomic() {
    let mut g = game(5);
    for p in ["A2", "B1"] {
        put(&mut g, Color::Black, p);
    }
    let before = g.clone();
    assert_eq!(g.play_as(Color::White, mv(&g, "A1")), Err(Error::Suicide));
    assert_eq!(g, before);
}

fn ko_position() -> Game {
    let mut g = game(5);
    for p in ["A2", "B1", "C2"] {
        put(&mut g, Color::Black, p);
    }
    for p in ["B2", "A3", "C3", "B4"] {
        put(&mut g, Color::White, p);
    }
    assert_eq!(g.play(mv(&g, "B3")), Ok(1));
    g
}

#[test]
fn ko_blocks_immediate_recapture_but_allows_after_intervening_moves() {
    let mut g = ko_position();
    let before = g.clone();
    assert_eq!(g.play(mv(&g, "B2")), Err(Error::Ko));
    assert_eq!(g, before);
    g.play(mv(&g, "E5")).unwrap();
    g.play(mv(&g, "E1")).unwrap();
    assert_eq!(g.play(mv(&g, "B2")), Ok(1));
}

#[test]
fn passes_pause_for_scoring_and_resignation_records_winner() {
    let mut g = game(9);
    g.play(Move::Pass).unwrap();
    g.play(Move::Pass).unwrap();
    assert_eq!(g.phase(), Phase::AwaitingScoring);
    assert_eq!(g.play(mv(&g, "D4")), Err(Error::NotPlaying));
    assert_eq!(g.captures_by(Color::Black), 0);
    g.resume_play().unwrap();
    g.resign().unwrap();
    assert_eq!(
        g.phase(),
        Phase::Resigned {
            winner: Color::White
        }
    );
    assert!(g.to_sgf().contains("RE[W+R]"));
    assert!(g.play_as(Color::White, Move::Pass).is_err());
}

#[test]
fn sgf_export_has_correct_orientation_colors_and_empty_pass_value() {
    let mut g = Game::default();
    for text in ["A19", "T1", "pass"] {
        g.play(mv(&g, text)).unwrap();
    }
    let sgf = g.to_sgf();
    assert!(sgf.starts_with("(;FF[4]GM[1]CA[UTF-8]AP[goproverbs:0.1.0]SZ[19]KM[6.5]"));
    assert!(sgf.ends_with(";B[aa];W[ss];B[])"));
    assert!(!sgf.contains("RU["));
}

#[test]
fn ascii_fixture_orientation_and_star_points() {
    let mut g = game(9);
    for text in ["A9", "J1", "E5"] {
        g.play(mv(&g, text)).unwrap();
    }
    assert_eq!(
        g.board().to_ascii(),
        concat!(
            "  A B C D E F G H J\n",
            "9 X . . . . . . . . 9\n",
            "8 . . . . . . . . . 8\n",
            "7 . . + . . . + . . 7\n",
            "6 . . . . . . . . . 6\n",
            "5 . . . . X . . . . 5\n",
            "4 . . . . . . . . . 4\n",
            "3 . . + . . . + . . 3\n",
            "2 . . . . . . . . . 2\n",
            "1 . . . . . . . . O 1\n",
            "  A B C D E F G H J\n"
        )
    );
    for n in [9, 13, 19] {
        let board = game(n).board().to_ascii();
        assert!(board.is_ascii());
        assert_eq!(board.matches('+').count(), if n == 9 { 5 } else { 9 });
    }
}

#[test]
fn heuristic_rescues_atari_before_opening_and_does_not_mutate_game() {
    let mut g = game(9);
    put(&mut g, Color::Black, "B2");
    for p in ["A2", "C2", "B1"] {
        put(&mut g, Color::White, p);
    }
    let before = g.clone();
    let ranked = rank_moves(&g, Color::Black, &Weights::default());
    assert_eq!(ranked[0].action, mv(&g, "B3"));
    assert!(
        ranked[0]
            .contributions
            .iter()
            .any(|c| c.feature == "save_atari" && c.score > 0.0)
    );
    assert_eq!(g, before);
}

#[test]
fn heuristics_only_rank_legal_moves_and_weights_change_preference() {
    let g = ko_position();
    let ranked = rank_moves(&g, Color::White, &Weights::default());
    assert!(!ranked.iter().any(|c| c.action == mv(&g, "B2")));
    for candidate in ranked {
        assert!(g.clone().play(candidate.action).is_ok());
    }
    let g = game(19);
    let mut weights = Weights::default();
    let before = rank_moves(&g, Color::Black, &weights)[0].action;
    weights.set("empty_corner", -10.0).unwrap();
    assert_ne!(rank_moves(&g, Color::Black, &weights)[0].action, before);
    assert!(weights.set("capture", f64::NAN).is_err());
    assert!(weights.set("unknown", 1.0).is_err());
}

#[test]
fn modern_33_is_a_disabled_experimental_feature() {
    let mut g = game(19);
    put(&mut g, Color::Black, "D4");
    let ranked = rank_moves(&g, Color::White, &Weights::default());
    let invasion = ranked.iter().find(|c| c.action == mv(&g, "C3")).unwrap();
    let term = invasion
        .contributions
        .iter()
        .find(|c| c.feature == "early_33")
        .unwrap();
    assert_eq!(term.value, 1.0);
    assert_eq!(term.weight, 0.0);
}

#[test]
fn small_boards_and_short_self_play_never_produce_illegal_moves() {
    for n in [2, 3, 9] {
        let mut g = game(n);
        for _ in 0..60 {
            if g.phase() != Phase::Playing {
                break;
            }
            let ranked = rank_moves(&g, g.to_play(), &Weights::default());
            assert!(!ranked.is_empty());
            g.play(ranked[0].action).unwrap();
        }
    }
}

#[test]
fn eye_filling_penalty_distinguishes_false_corner_eye() {
    let mut g = game(9);
    for p in ["B1", "A2", "B2"] {
        put(&mut g, Color::Black, p);
    }
    let ranked = rank_moves(&g, Color::Black, &Weights::default());
    let fill = ranked.iter().find(|c| c.action == mv(&g, "A1")).unwrap();
    assert!(
        fill.contributions
            .iter()
            .any(|c| c.feature == "fill_eye" && c.score < 0.0)
    );
    assert_ne!(ranked[0].action, fill.action);

    let mut false_eye = game(9);
    for p in ["B1", "A2"] {
        put(&mut false_eye, Color::Black, p);
    }
    put(&mut false_eye, Color::White, "B2");
    let ranked = rank_moves(&false_eye, Color::Black, &Weights::default());
    let connection = ranked
        .iter()
        .find(|c| c.action == mv(&false_eye, "A1"))
        .unwrap();
    assert!(
        !connection
            .contributions
            .iter()
            .any(|c| c.feature == "fill_eye")
    );
    assert!(
        connection
            .contributions
            .iter()
            .any(|c| c.feature == "connect" && c.score > 0.0)
    );
}

#[test]
fn self_atari_is_penalized_but_remains_a_legal_candidate() {
    let mut g = game(9);
    put(&mut g, Color::Black, "A2");
    let ranked = rank_moves(&g, Color::White, &Weights::default());
    let atari = ranked.iter().find(|c| c.action == mv(&g, "A1")).unwrap();
    assert!(
        atari
            .contributions
            .iter()
            .any(|c| c.feature == "self_atari" && c.score < 0.0)
    );
    assert!(g.play_as(Color::White, atari.action).is_ok());
}
