use goproverbs::gtp::Engine;
use std::sync::atomic::{AtomicUsize, Ordering};

static NEXT: AtomicUsize = AtomicUsize::new(0);
struct Fixture(std::path::PathBuf);
impl Fixture {
    fn new(text: &str) -> Self {
        let path = std::env::temp_dir().join(format!(
            "gp-sgf-{}-{}.sgf",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::write(&path, text).unwrap();
        Self(path)
    }
    fn load(&self, suffix: &str) -> String {
        format!("loadsgf {}{suffix}", self.0.display())
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}
fn command(engine: &mut Engine, text: &str) -> String {
    engine.handle_line(text).unwrap().text
}

#[test]
fn loadsgf_move_number_undo_and_clock() {
    let file = Fixture::new("(;FF[4]SZ[9]KM[6.5]RU[TT];B[aa];W[bb];B[])");
    let mut engine = Engine::default();
    assert_eq!(command(&mut engine, "known_command loadsgf"), "= true\n\n");
    command(&mut engine, "time_settings 120 0 0");
    let budget = command(&mut engine, "gp-time-budget B");
    for (suffix, count) in [(" 1", 0), (" 2", 1), (" 3", 2), (" 99", 3), ("", 3)] {
        assert_eq!(command(&mut engine, &file.load(suffix)), "=\n\n");
        assert_eq!(engine.game().history().len(), count);
        assert_eq!(engine.game().komi(), 6.5);
        assert_eq!(engine.game().board().size().get(), 9);
        assert_eq!(command(&mut engine, "gp-time-budget B"), budget);
    }
    for count in (0..3).rev() {
        assert_eq!(command(&mut engine, "undo"), "=\n\n");
        assert_eq!(engine.game().history().len(), count);
    }
    assert_eq!(command(&mut engine, "undo"), "? cannot undo\n\n");
}

#[test]
fn failed_load_is_atomic_including_undo() {
    let bad = Fixture::new("(;SZ[9]KM[9.5]RU[TT];B[aa];W[aa])");
    let mut engine = Engine::default();
    command(&mut engine, "play B D4");
    let before = engine.game().clone();
    assert_eq!(
        command(&mut engine, &bad.load("")),
        "? cannot load file\n\n"
    );
    assert_eq!(engine.game(), &before);
    for suffix in [" 0", " -1", " x", " 1 extra"] {
        assert_eq!(
            command(&mut engine, &bad.load(suffix)),
            "? syntax error\n\n"
        );
        assert_eq!(engine.game(), &before);
    }
    assert_eq!(command(&mut engine, "undo"), "=\n\n");
    assert!(engine.game().history().is_empty());
}
