use goproverbs::external::LocalEvaluator;
use goproverbs::search::LeafEvaluator;
use goproverbs::{BoardSize, Color, Error, Game, Move, Rules};
use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::thread;
use std::time::{Duration, Instant};

fn game() -> Game {
    Game::with_rules(BoardSize::new(5).unwrap(), 0.5, Rules::TrompTaylor).unwrap()
}

#[test]
fn expired_deadline_never_connects() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    listener.set_nonblocking(true).unwrap();
    let mut evaluator = LocalEvaluator(listener.local_addr().unwrap().port());
    assert_eq!(evaluator.evaluate(&game(), Instant::now()), None);
    assert_eq!(
        listener.accept().unwrap_err().kind(),
        std::io::ErrorKind::WouldBlock
    );
}

#[test]
fn slow_drip_cannot_extend_total_deadline() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let mut evaluator = LocalEvaluator(listener.local_addr().unwrap().port());
    let server = thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        let mut request = String::new();
        BufReader::new(stream.try_clone().unwrap())
            .read_line(&mut request)
            .unwrap();
        for _ in 0..10 {
            thread::sleep(Duration::from_millis(30));
            if stream.write_all(b"1").is_err() {
                break;
            }
        }
    });
    let start = Instant::now();
    assert_eq!(
        evaluator.evaluate(&game(), start + Duration::from_millis(80)),
        None
    );
    assert!(start.elapsed() < Duration::from_millis(220));
    server.join().unwrap();
}

#[test]
fn bridge_sends_complete_ko_history_and_finite_value() {
    let mut g = game();
    for (color, points) in [
        (Color::Black, vec!["A2", "B1", "C2"]),
        (Color::White, vec!["B2", "A3", "C3", "B4"]),
    ] {
        for point in points {
            g.play_as(color, Move::from_gtp(point, g.board().size()).unwrap())
                .unwrap();
        }
    }
    g.play_as(
        Color::Black,
        Move::from_gtp("B3", g.board().size()).unwrap(),
    )
    .unwrap();
    g.play(Move::Pass).unwrap();
    let before = g.clone();
    assert_eq!(
        g.play_as(
            Color::White,
            Move::from_gtp("B2", g.board().size()).unwrap()
        ),
        Err(Error::Ko)
    );
    assert_eq!(g, before);
    let expected = g.to_sgf();
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let mut evaluator = LocalEvaluator(listener.local_addr().unwrap().port());
    let server = thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        let mut request = String::new();
        BufReader::new(stream.try_clone().unwrap())
            .read_line(&mut request)
            .unwrap();
        let fields: Vec<_> = request.trim().splitn(4, ' ').collect();
        assert_eq!(&fields[..2], &["EVAL2", "B"]);
        assert!(fields[2].parse::<u128>().unwrap() > 0);
        assert_eq!(fields[3], expected);
        stream.write_all(b"8.5\n").unwrap();
    });
    assert_eq!(
        evaluator.evaluate(&g, Instant::now() + Duration::from_secs(2)),
        Some(8.5)
    );
    server.join().unwrap();
}

#[test]
fn malformed_or_nonfinite_response_is_not_an_evaluation() {
    for answer in ["NaN\n", "error\n", "inf\n"] {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let mut evaluator = LocalEvaluator(listener.local_addr().unwrap().port());
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut request = String::new();
            BufReader::new(stream.try_clone().unwrap())
                .read_line(&mut request)
                .unwrap();
            stream.write_all(answer.as_bytes()).unwrap();
        });
        assert_eq!(
            evaluator.evaluate(&game(), Instant::now() + Duration::from_secs(2)),
            None
        );
        server.join().unwrap();
    }
}
