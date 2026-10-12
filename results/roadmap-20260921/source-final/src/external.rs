//! Optional localhost evaluation bridge. No model/runtime dependency in Rust.
use crate::{Color, Game, search::LeafEvaluator};
use std::io::{BufRead, BufReader, Write};
use std::net::{Ipv4Addr, SocketAddr, TcpStream};
use std::time::Instant;

pub struct LocalEvaluator(pub u16);

impl LeafEvaluator for LocalEvaluator {
    fn evaluate(&mut self, game: &Game, deadline: Instant) -> Option<f64> {
        let remaining = deadline.checked_duration_since(Instant::now())?;
        if remaining.is_zero() {
            return None;
        }
        let address = SocketAddr::from((Ipv4Addr::LOCALHOST, self.0));
        let mut stream = TcpStream::connect_timeout(&address, remaining).ok()?;
        stream.set_read_timeout(Some(remaining)).ok()?;
        stream.set_write_timeout(Some(remaining)).ok()?;
        let color = if game.to_play() == Color::Black {
            "B"
        } else {
            "W"
        };
        writeln!(stream, "EVAL {color} {}", game.to_sgf()).ok()?;
        let mut line = String::new();
        BufReader::new(stream).read_line(&mut line).ok()?;
        let value = line.trim().parse::<f64>().ok()?;
        value.is_finite().then_some(value)
    }
}
