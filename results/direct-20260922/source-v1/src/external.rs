//! Optional localhost evaluation bridge. No model/runtime dependency in Rust.
use crate::{Color, Game, search::LeafEvaluator};
use std::io::{Read, Write};
use std::net::{Ipv4Addr, SocketAddr, TcpStream};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

pub struct LocalEvaluator(pub u16);

impl LeafEvaluator for LocalEvaluator {
    fn evaluate(&mut self, game: &Game, deadline: Instant) -> Option<f64> {
        let remaining = deadline.checked_duration_since(Instant::now())?;
        if remaining.is_zero() {
            return None;
        }
        let address = SocketAddr::from((Ipv4Addr::LOCALHOST, self.0));
        let mut stream = TcpStream::connect_timeout(&address, remaining).ok()?;
        let color = if game.to_play() == Color::Black {
            "B"
        } else {
            "W"
        };
        // Absolute host wall time lets the broker discard requests that expired
        // in its accept queue. Rust's monotonic deadline remains authoritative.
        let sgf = game.to_sgf();
        let remaining = deadline.checked_duration_since(Instant::now())?;
        let expires = SystemTime::now().checked_add(remaining)?;
        let expires_us = expires.duration_since(UNIX_EPOCH).ok()?.as_micros();
        let request = format!("EVAL2 {color} {expires_us} {sgf}\n");
        let mut pending = request.as_bytes();
        while !pending.is_empty() {
            let remaining = deadline.checked_duration_since(Instant::now())?;
            stream.set_write_timeout(Some(remaining)).ok()?;
            let written = stream.write(pending).ok()?;
            if written == 0 {
                return None;
            }
            pending = &pending[written..];
        }
        let mut line = Vec::new();
        loop {
            let remaining = deadline.checked_duration_since(Instant::now())?;
            stream.set_read_timeout(Some(remaining)).ok()?;
            let mut buffer = [0; 64];
            let read = stream.read(&mut buffer).ok()?;
            if read == 0 {
                return None;
            }
            line.extend_from_slice(&buffer[..read]);
            if line.len() > 128 {
                return None;
            }
            if line.contains(&b'\n') {
                break;
            }
        }
        if Instant::now() >= deadline {
            return None;
        }
        let value = std::str::from_utf8(&line)
            .ok()?
            .trim()
            .parse::<f64>()
            .ok()?;
        value.is_finite().then_some(value)
    }
}
