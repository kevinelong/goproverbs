//! Composed engineering cases, not expert-reviewed strategic labels.
use goproverbs::engine::{Weights, rank_moves};
use goproverbs::{BoardSize, Color, Game, Move, Rules};

fn game(size: u8) -> Game {
    Game::with_rules(BoardSize::new(size).unwrap(), 0.0, Rules::TrompTaylor).unwrap()
}
fn play(game: &mut Game, color: Color, point: &str) {
    game.play_as(color, Move::from_gtp(point, game.board().size()).unwrap())
        .unwrap();
}

#[test]
fn mutual_liberties_have_neutral_area_and_each_invasion_has_a_capture_reply() {
    // Two diagonal stones on 2x2 share both remaining liberties. This finite
    // case checks the mutual-capture mechanism; it is not a general seki solver.
    let mut position = game(2);
    play(&mut position, Color::Black, "A1");
    play(&mut position, Color::White, "B2");
    let score = position.board().area_score(0.0);
    assert_eq!((score.black, score.white, score.neutral), (1, 1, 2));
    for (attacker, defender) in [(Color::Black, Color::White), (Color::White, Color::Black)] {
        for (first, reply) in [("A2", "B1"), ("B1", "A2")] {
            let mut branch = position.clone();
            play(&mut branch, attacker, first);
            play(&mut branch, defender, reply);
            assert_eq!(branch.captures_by(defender), 2);
        }
    }
    play(&mut position, Color::Black, "pass");
    play(&mut position, Color::White, "pass");
    assert_eq!(position.final_result().as_deref(), Some("0"));
}

#[test]
fn a_real_connection_is_distinct_from_redundant_shape_filling() {
    let mut separated = game(5);
    for point in ["B2", "D2"] {
        play(&mut separated, Color::Black, point);
    }
    let mut connected = separated.clone();
    for point in ["B3", "C3", "D3"] {
        play(&mut connected, Color::Black, point);
    }
    let contribution = |g: &Game| {
        let move_ = Move::from_gtp("C2", g.board().size()).unwrap();
        rank_moves(g, Color::Black, &Weights::default())
            .into_iter()
            .find(|candidate| candidate.action == move_)
            .unwrap()
            .contributions
            .into_iter()
            .find(|term| term.feature == "connect")
            .map_or(0.0, |term| term.value)
    };
    assert!(contribution(&separated) > 0.0);
    assert_eq!(contribution(&connected), 0.0);
}

#[test]
fn filling_safe_owned_area_does_not_create_an_extra_tt_point() {
    let mut position = game(5);
    for point in ["B1", "C2", "B3", "A2"] {
        play(&mut position, Color::Black, point);
    }
    play(&mut position, Color::White, "E5");
    let before = position.board().area_score(0.0);
    play(&mut position, Color::Black, "B2");
    let after = position.board().area_score(0.0);
    assert_eq!(before, after);
}
