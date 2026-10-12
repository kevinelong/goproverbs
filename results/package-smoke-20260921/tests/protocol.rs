use goproverbs::gtp::{Engine, serve};
use goproverbs::{Color, Move, Point};

fn command(engine: &mut Engine, text: &str) -> String {
    engine.handle_line(text).unwrap().text
}

#[test]
fn stream_framing_comments_ids_and_quit() {
    let mut output = Vec::new();
    serve(
        &b"# comment\n\n1\tprotocol_version\r\n2 name # ignored\n3 unknown\n4 quit\n5 name\n"[..],
        &mut output,
    )
    .unwrap();
    assert_eq!(
        String::from_utf8(output).unwrap(),
        "=1 2\n\n=2 goproverbs\n\n?3 unknown command\n\n=4\n\n"
    );
}

#[test]
fn required_commands_and_invalid_arguments() {
    let mut e = Engine::default();
    for cmd in [
        "protocol_version",
        "name",
        "version",
        "known_command",
        "list_commands",
        "quit",
        "boardsize",
        "clear_board",
        "komi",
        "play",
        "genmove",
    ] {
        assert_eq!(
            command(&mut e, &format!("known_command {cmd}")),
            "= true\n\n"
        );
    }
    assert_eq!(command(&mut e, "known_command final_score"), "= true\n\n");
    for cmd in [
        "play",
        "play blue D4",
        "boardsize 0",
        "boardsize 26",
        "komi NaN",
        "quit extra",
        "gp-weight capture inf",
    ] {
        assert!(command(&mut e, cmd).starts_with('?'), "{cmd}");
    }
}

#[test]
fn explicit_colors_undo_and_komi_preservation() {
    let mut e = Engine::default();
    assert_eq!(command(&mut e, "play b D4"), "=\n\n");
    assert_eq!(command(&mut e, "play b Q16"), "=\n\n");
    assert_eq!(e.game().history().len(), 2);
    command(&mut e, "komi 7.5");
    command(&mut e, "undo");
    assert_eq!(e.game().history().len(), 1);
    assert_eq!(e.game().komi(), 7.5);
    let before = e.game().clone();
    assert_eq!(command(&mut e, "play w D4"), "? illegal move\n\n");
    assert_eq!(e.game(), &before);
    command(&mut e, "clear_board");
    assert!(e.game().history().is_empty());
    assert_eq!(e.game().komi(), 7.5);
    assert_eq!(command(&mut e, "undo"), "? cannot undo\n\n");
}

#[test]
fn generate_explain_export_and_resume_after_passes() {
    let mut e = Engine::default();
    command(&mut e, "boardsize 9");
    let before = e.game().clone();
    let explanation = command(&mut e, "gp-explain b C3");
    assert!(!explanation.contains("empty_corner"));
    assert!(explanation.contains("C3:"));
    assert_eq!(e.game(), &before);
    let response = command(&mut e, "9 genmove white");
    assert!(response.starts_with("=9 "));
    let p = Point::from_gtp(
        response.trim().strip_prefix("=9 ").unwrap(),
        e.game().board().size(),
    )
    .unwrap();
    assert_eq!(e.game().board().at(p), Ok(Some(Color::White)));
    assert!(command(&mut e, "showboard").starts_with("= \n  A B C D E F G H J\n"));
    assert!(command(&mut e, "gp-sgf").contains("FF[4]GM[1]"));
    assert_eq!(command(&mut e, "play b pass"), "=\n\n");
    assert_eq!(command(&mut e, "play w pass"), "=\n\n");
    assert!(command(&mut e, "genmove b").starts_with("= "));
    assert!(matches!(
        e.game().history().last().unwrap().action,
        Move::Play(_)
    ));
}
