use crate::coords::COLUMNS;
use crate::{Board, Color, Game, Phase, Point};
use std::fmt::Write;

impl Board {
    /// GNU Go-style ASCII symbols and GTP-oriented edge labels.
    pub fn to_ascii(&self) -> String {
        let size = self.size();
        let n = size.get();
        let width = n.to_string().len();
        let labels = COLUMNS[..usize::from(n)]
            .iter()
            .map(|&c| (c as char).to_string())
            .collect::<Vec<_>>()
            .join(" ");
        let header = format!("{}{}\n", " ".repeat(width + 1), labels);
        let mut out = header.clone();
        for row in 0..n {
            write!(out, "{:>width$} ", n - row).unwrap();
            for col in 0..n {
                let p = Point::new(col, row, size).expect("in bounds");
                let symbol = match self.at(p).expect("in bounds") {
                    Some(Color::Black) => 'X',
                    Some(Color::White) => 'O',
                    None if is_star(n, col, row) => '+',
                    None => '.',
                };
                write!(out, "{symbol} ").unwrap();
            }
            writeln!(out, "{:>width$}", n - row).unwrap();
        }
        out.push_str(&header);
        out
    }
}

// Conventional five points on 9x9; nine on 13x13 and 19x19.
// Other supported sizes get no decorative star points.
fn is_star(size: u8, col: u8, row: u8) -> bool {
    match size {
        9 => ([2, 6].contains(&col) && [2, 6].contains(&row)) || (col == 4 && row == 4),
        13 => [3, 6, 9].contains(&col) && [3, 6, 9].contains(&row),
        19 => [3, 9, 15].contains(&col) && [3, 9, 15].contains(&row),
        _ => false,
    }
}

impl Game {
    pub fn to_ascii(&self) -> String {
        let mut out = self.board().to_ascii();
        writeln!(out, "\nX Black | O White | . empty | + star point").unwrap();
        writeln!(
            out,
            "Moves: {} | Komi: {} | Captures: Black {}, White {}",
            self.history().len(),
            self.komi(),
            self.captures_by(Color::Black),
            self.captures_by(Color::White)
        )
        .unwrap();
        match self.phase() {
            Phase::Finished => writeln!(
                out,
                "Final result: {} (Tromp-Taylor area)",
                self.final_result().unwrap()
            ),
            Phase::Playing => writeln!(out, "To play: {}", self.to_play()),
            Phase::AwaitingScoring => {
                writeln!(out, "Two passes: awaiting scoring (not implemented)")
            }
            Phase::Resigned { winner } => writeln!(out, "{winner} wins by resignation"),
        }
        .unwrap();
        out
    }
}
