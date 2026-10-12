//! Go board mechanics, GTP coordinates, ASCII display, and SGF FF[4] export.
//! This foundation uses simple ko and forbids suicide. It is not a complete
//! implementation of Japanese, Chinese, AGA, or BGA tournament rules.

mod ascii;
pub mod clock;
mod coords;
pub mod engine;
pub mod external;
mod game;
pub mod gtp;
pub mod scoring;
pub mod search;
mod sgf;
pub mod sgf_import;

pub use coords::{BoardSize, Move, Point};
pub use game::{Board, Color, Game, Group, MoveRecord, Phase, Rules};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    InvalidSize,
    InvalidCoordinate,
    OutOfBounds,
    Occupied,
    Suicide,
    Ko,
    NotPlaying,
    InvalidKomi,
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Self::InvalidSize => "board size must be between 2 and 25",
            Self::InvalidCoordinate => "expected a coordinate such as D4 (skip I), or pass",
            Self::OutOfBounds => "point is outside this board",
            Self::Occupied => "intersection is occupied",
            Self::Suicide => "self-capture is illegal",
            Self::Ko => "repetition is forbidden by the selected ko rule",
            Self::NotPlaying => "game is awaiting scoring or has ended",
            Self::InvalidKomi => "komi must be finite",
        })
    }
}

impl std::error::Error for Error {}
