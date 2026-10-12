use goproverbs::{Color, clock::TimeControl, gtp::Engine};

#[test]
fn absolute_canadian_and_unlimited_allocations() {
    let mut clock = TimeControl::default();
    assert_eq!(clock.budget(Color::Black, 1000), 1000);
    clock.configure(30, 0, 0);
    assert_eq!(clock.budget(Color::Black, 1000), 990);
    clock.update(Color::Black, 1, 0);
    assert_eq!(clock.budget(Color::Black, 1000), 23);
    assert_eq!(clock.budget(Color::White, 1000), 990);
    clock.configure(0, 10, 5);
    assert_eq!(clock.budget(Color::Black, 10000), 1990);
    for _ in 0..5 {
        clock.charge(Color::Black, 1000);
    }
    assert_eq!(clock.budget(Color::Black, 10000), 1990);
    clock.configure(0, 1, 0);
    assert_eq!(clock.budget(Color::Black, 1000), 1000);
    clock.configure(1, 10, 1);
    clock.charge(Color::Black, 1500);
    assert_eq!(clock.budget(Color::Black, 10000), 9990);
    clock.charge(Color::Black, 11000);
    clock.charge(Color::Black, 0);
    assert_eq!(clock.budget(Color::Black, 10000), 0);
    clock.update(Color::Black, 10, 1);
    assert_eq!(clock.budget(Color::Black, 10000), 9990);
    clock.configure(0, 0, 0);
    assert_eq!(clock.budget(Color::Black, 1000), 0);
}

#[test]
fn invalid_protocol_clock_update_is_atomic_and_analysis_does_not_charge() {
    let mut engine = Engine::default();
    let call = |e: &mut Engine, s: &str| e.handle_line(s).unwrap().text;
    assert_eq!(call(&mut engine, "time_settings 30 0 0"), "=\n\n");
    assert_eq!(call(&mut engine, "gp-time-budget B"), "= 990\n\n");
    assert!(call(&mut engine, "gp-search B").starts_with('='));
    assert_eq!(call(&mut engine, "gp-time-budget B"), "= 990\n\n");
    assert!(call(&mut engine, "time_left B -1 0").starts_with('?'));
    assert!(call(&mut engine, "time_settings 0 0 bad").starts_with('?'));
    assert_eq!(call(&mut engine, "gp-time-budget B"), "= 990\n\n");
    call(&mut engine, "time_left B 0 0");
    let before = engine.game().clone();
    assert!(call(&mut engine, "genmove B").starts_with('='));
    assert_ne!(engine.game(), &before);
    assert!(call(&mut engine, "gp-last-search").contains("clock_budget_ms=0"));
}
