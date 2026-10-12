use crate::{Color, Game, Rules};
use std::fmt::Write;

impl Game {
    /// Export this game's main line, not a general-purpose SGF document editor.
    pub fn to_sgf(&self) -> String {
        let mut out = format!(
            "(;FF[4]GM[1]CA[UTF-8]AP[goproverbs:{}]SZ[{}]KM[{}]",
            env!("CARGO_PKG_VERSION"),
            self.board().size().get(),
            self.komi()
        );
        match self.rules() {
            Rules::TrompTaylor => out.push_str("RU[Tromp-Taylor]"),
            Rules::SimpleKoNoSuicide => {
                out.push_str("C[Simple ko; suicide forbidden; scoring not implemented.]")
            }
        }
        if let Some(result) = self.final_result() {
            write!(out, "RE[{result}]").unwrap();
        }
        for record in self.history() {
            write!(
                out,
                ";{}[{}]",
                sgf_color(record.color),
                record
                    .action
                    .to_sgf(self.board().size())
                    .expect("validated move")
            )
            .unwrap();
        }
        out.push(')');
        out
    }
}

fn sgf_color(color: Color) -> char {
    match color {
        Color::Black => 'B',
        Color::White => 'W',
    }
}
