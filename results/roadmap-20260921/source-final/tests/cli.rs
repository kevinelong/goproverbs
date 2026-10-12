use std::process::Command;

#[test]
fn cli_renders_exports_and_reports_bad_moves() {
    let exe = env!("CARGO_BIN_EXE_goproverbs");
    let board = Command::new(exe)
        .args(["--size", "9", "A9", "J1"])
        .output()
        .unwrap();
    assert!(board.status.success());
    let text = String::from_utf8(board.stdout).unwrap();
    assert!(text.contains("9 X . . . . . . . . 9"));
    assert!(text.contains("1 . . . . . . . . O 1"));
    let sgf = Command::new(exe)
        .args(["--sgf", "D4", "Q16", "pass"])
        .output()
        .unwrap();
    assert!(sgf.status.success());
    assert!(
        String::from_utf8(sgf.stdout)
            .unwrap()
            .ends_with(";B[dp];W[pd];B[])\n")
    );
    let bad = Command::new(exe).args(["D4", "D4"]).output().unwrap();
    assert!(!bad.status.success());
    assert!(bad.stdout.is_empty());
    assert!(String::from_utf8(bad.stderr).unwrap().contains("occupied"));
}
