use goproverbs::{BoardSize, Color, Error, Game, Move, Phase, Rules, sgf_import};

#[test]
fn first_game_and_first_variation_determine_history() {
    let game = sgf_import::parse(
        "(;FF[4]GM[1]SZ[9:9]KM[7.5]RU[Tromp-Taylor];B[aa](;W[bb];B[cc])(;W[aa]))(;GM[2])",
        None,
    )
    .unwrap();
    assert_eq!(game.board().size().get(), 9);
    assert_eq!(game.komi(), 7.5);
    assert_eq!(game.history().len(), 3);
    assert_eq!(
        game.history()[1]
            .action
            .to_sgf(game.board().size())
            .unwrap(),
        "bb"
    );
    assert_eq!(game.to_play(), Color::White);
}

#[test]
fn export_import_round_trip_preserves_complete_game_and_history() {
    let mut game = Game::with_rules(BoardSize::new(5).unwrap(), -0.5, Rules::TrompTaylor).unwrap();
    for text in ["A1", "B1", "C3", "pass", "pass"] {
        game.play(Move::from_gtp(text, game.board().size()).unwrap())
            .unwrap();
    }
    assert_eq!(sgf_import::parse(&game.to_sgf(), None).unwrap(), game);
    assert_eq!(game.phase(), Phase::Finished);
}

#[test]
fn escaped_delimiters_utf8_comments_and_line_continuations_are_safe() {
    let game = sgf_import::parse(
        "\u{feff}(;RU[Tromp-\\\r\nTaylor]C[escaped \\] \\\\ (; \u{1f383}\n]SZ[9];B[a\\\na])",
        None,
    )
    .unwrap();
    assert_eq!(game.history().len(), 1);
    assert_eq!(
        game.history()[0]
            .action
            .to_sgf(game.board().size())
            .unwrap(),
        "aa"
    );
    assert!(sgf_import::parse("(;RU[TT];B[\u{e9}])", None).is_err());
}

#[test]
fn limits_count_moves_not_comment_nodes_and_still_validate_remainder() {
    let text = "(;RU[TT]SZ[9];C[before];B[aa];C[after];W[bb])";
    assert_eq!(sgf_import::parse(text, Some(0)).unwrap().history().len(), 0);
    let one = sgf_import::parse(text, Some(1)).unwrap();
    assert_eq!(one.history().len(), 1);
    assert_eq!(one.to_play(), Color::White);
    assert_eq!(
        sgf_import::parse(text, Some(99)).unwrap().history().len(),
        2
    );
    assert!(sgf_import::parse("(;RU[TT];B[aa];W[aa])", Some(1)).is_err());
}

#[test]
fn legacy_pass_is_only_pass_on_boards_up_to_nineteen() {
    let small = sgf_import::parse("(;RU[TT];B[tt];W[])", None).unwrap();
    assert_eq!(small.phase(), Phase::Finished);
    let large = sgf_import::parse("(;RU[TT]SZ[25];B[tt])", None).unwrap();
    assert!(matches!(large.history()[0].action, Move::Play(_)));
}

#[test]
fn malformed_syntax_is_rejected_even_in_unselected_trees() {
    for text in [
        "",
        "()",
        "(;RU[TT]",
        "(;RU[TT])junk",
        "(;RU[TT]C[unterminated)",
        "(;RU[TT]C[escape\\",
        "(;RU[TT]SZ)",
        "(;RU[TT]SZ[9]SZ[9])",
        "(;RU[TT](;B[aa])())",
        "(;RU[TT])(;C[broken)",
        "(;RU[TT]c[lowercase])",
    ] {
        assert!(sgf_import::parse(text, None).is_err(), "{text}");
    }
    let deep = format!("{}{}", "(;".repeat(130), ")".repeat(130));
    assert!(sgf_import::parse(&deep, None).is_err());
}

#[test]
fn unsupported_semantics_and_invalid_settings_are_explicit_errors() {
    for property in [
        "RU[Japanese]",
        "FF[3]",
        "GM[2]",
        "SZ[1]",
        "SZ[26]",
        "SZ[9:13]",
        "SZ[9:9:9]",
        "KM[NaN]",
        "KM[inf]",
        "KM[bad]",
        "AB[aa]",
        "AW[bb]",
        "AE[aa]",
        "HA[0]",
        "PL[W]",
        "CA[ISO-8859-1]",
        "SZ[9][13]",
    ] {
        let text = if property.starts_with("RU") {
            format!("(;{property})")
        } else {
            format!("(;RU[TT]{property})")
        };
        assert!(sgf_import::parse(&text, None).is_err(), "{text}");
    }
    assert!(sgf_import::parse("(;SZ[9])", None).is_err());
    for suffix in [
        "SZ[9]",
        "KM[1]",
        "RU[TT]",
        "PL[B]",
        "AB[aa]",
        "B[aa]W[bb]",
        "B[aa][bb]",
    ] {
        assert!(sgf_import::parse(&format!("(;RU[TT];{suffix})"), None).is_err());
    }
}

#[test]
fn illegal_moves_and_play_after_termination_are_rejected() {
    for text in [
        "(;RU[TT]SZ[9];B[jj])",
        "(;RU[TT];B[aa];W[aa])",
        "(;RU[TT];B[];W[];B[aa])",
        "(;RU[TT];B[resign])",
    ] {
        assert!(sgf_import::parse(text, None).is_err(), "{text}");
    }
}

#[test]
fn imported_ko_retains_repetition_history_including_same_color_moves() {
    let text = "(;RU[TT]SZ[5];B[ad];B[be];B[cd];W[bd];W[ac];W[cc];W[bb];B[bc])";
    let mut game = sgf_import::parse(text, None).unwrap();
    assert_eq!(game.history().len(), 8);
    assert_eq!(game.captures_by(Color::Black), 1);
    let recapture = Move::from_sgf("bd", game.board().size()).unwrap();
    assert_eq!(game.play_as(Color::White, recapture), Err(Error::Ko));
    let illegal = text.replace(")", ";W[bd])");
    assert!(sgf_import::parse(&illegal, None).is_err());
    let before_capture = sgf_import::parse(text, Some(7)).unwrap();
    assert_eq!(before_capture.captures_by(Color::Black), 0);
}
