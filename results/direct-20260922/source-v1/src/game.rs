use crate::{BoardSize, Error, Move, Point};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Color {
    Black,
    White,
}

impl Color {
    pub fn opponent(self) -> Self {
        match self {
            Self::Black => Self::White,
            Self::White => Self::Black,
        }
    }
    pub(crate) fn index(self) -> usize {
        match self {
            Self::Black => 0,
            Self::White => 1,
        }
    }
}

impl std::fmt::Display for Color {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Self::Black => "Black",
            Self::White => "White",
        })
    }
}

/// Explicit policy; no claim of implementing a complete national ruleset.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Rules {
    SimpleKoNoSuicide,
    TrompTaylor,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase {
    Playing,
    AwaitingScoring,
    Finished,
    Resigned { winner: Color },
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Group {
    pub color: Color,
    pub stones: Vec<Point>,
    pub liberties: Vec<Point>,
}

/// A contiguous row-major array; board mutations are owned by Game.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Board {
    size: BoardSize,
    cells: Vec<Option<Color>>,
}

impl Board {
    pub fn new(size: BoardSize) -> Self {
        Self {
            size,
            cells: vec![None; size.area()],
        }
    }
    pub fn size(&self) -> BoardSize {
        self.size
    }
    pub fn at(&self, point: Point) -> Result<Option<Color>, Error> {
        Ok(self.cells[point.index(self.size)?])
    }

    pub(crate) fn neighbors(&self, index: usize) -> impl Iterator<Item = usize> {
        let n = usize::from(self.size.get());
        let (x, y) = (index % n, index / n);
        [
            if x > 0 { Some(index - 1) } else { None },
            if x + 1 < n { Some(index + 1) } else { None },
            if y > 0 { Some(index - n) } else { None },
            if y + 1 < n { Some(index + n) } else { None },
        ]
        .into_iter()
        .flatten()
    }

    /// Orthogonal connectivity; each liberty appears once even if shared.
    pub fn group_at(&self, point: Point) -> Result<Option<Group>, Error> {
        let start = point.index(self.size)?;
        let Some(color) = self.cells[start] else {
            return Ok(None);
        };
        let mut seen = vec![false; self.cells.len()];
        let mut liberty_seen = vec![false; self.cells.len()];
        let mut stack = vec![start];
        let mut group = Group {
            color,
            stones: Vec::new(),
            liberties: Vec::new(),
        };
        seen[start] = true;
        while let Some(index) = stack.pop() {
            group.stones.push(Point::from_index(index, self.size));
            for adjacent in self.neighbors(index) {
                match self.cells[adjacent] {
                    None if !liberty_seen[adjacent] => {
                        liberty_seen[adjacent] = true;
                        group.liberties.push(Point::from_index(adjacent, self.size));
                    }
                    Some(c) if c == color && !seen[adjacent] => {
                        seen[adjacent] = true;
                        stack.push(adjacent);
                    }
                    _ => {}
                }
            }
        }
        Ok(Some(group))
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MoveRecord {
    pub color: Color,
    pub action: Move,
    pub captured: Vec<Point>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Game {
    board: Board,
    to_play: Color,
    komi: f64,
    captures: [usize; 2],
    history: Vec<MoveRecord>,
    previous_board: Option<Board>,
    consecutive_passes: u8,
    phase: Phase,
    rules: Rules,
    positions: Vec<std::sync::Arc<Board>>,
}

impl Default for Game {
    fn default() -> Self {
        Self::new(BoardSize::default(), 6.5).expect("valid defaults")
    }
}

impl Game {
    pub fn new(size: BoardSize, komi: f64) -> Result<Self, Error> {
        Self::with_rules(size, komi, Rules::SimpleKoNoSuicide)
    }

    pub fn with_rules(size: BoardSize, komi: f64, rules: Rules) -> Result<Self, Error> {
        if !komi.is_finite() {
            return Err(Error::InvalidKomi);
        }
        Ok(Self {
            board: Board::new(size),
            to_play: Color::Black,
            komi,
            captures: [0; 2],
            history: Vec::new(),
            previous_board: None,
            consecutive_passes: 0,
            phase: Phase::Playing,
            rules,
            positions: vec![std::sync::Arc::new(Board::new(size))],
        })
    }

    pub fn board(&self) -> &Board {
        &self.board
    }
    pub fn to_play(&self) -> Color {
        self.to_play
    }
    pub fn komi(&self) -> f64 {
        self.komi
    }
    pub fn rules(&self) -> Rules {
        self.rules
    }
    pub fn phase(&self) -> Phase {
        self.phase
    }
    pub fn captures_by(&self, color: Color) -> usize {
        self.captures[color.index()]
    }
    pub fn history(&self) -> &[MoveRecord] {
        &self.history
    }

    pub fn set_komi(&mut self, komi: f64) -> Result<(), Error> {
        if !komi.is_finite() {
            return Err(Error::InvalidKomi);
        }
        self.komi = komi;
        Ok(())
    }

    /// GTP permits explicitly colored moves, including consecutive same-color
    /// moves and continuing after passes. Normal `play` still alternates turns.
    pub fn play_as(&mut self, color: Color, action: Move) -> Result<usize, Error> {
        let mut next = self.for_color(color);
        let captured = next.play(action)?;
        *self = next;
        Ok(captured)
    }

    pub(crate) fn for_color(&self, color: Color) -> Self {
        let mut next = self.clone();
        if next.to_play != color {
            next.previous_board = None;
            next.consecutive_passes = 0;
        }
        next.to_play = color;
        if next.phase == Phase::AwaitingScoring {
            next.phase = Phase::Playing;
            next.consecutive_passes = 0;
        }
        next
    }

    /// Apply one move atomically. On failure every part of the game is unchanged.
    /// Returns the number of opposing stones captured by this move.
    pub fn play(&mut self, action: Move) -> Result<usize, Error> {
        if self.phase != Phase::Playing {
            return Err(Error::NotPlaying);
        }
        let mut next = self.board.clone();
        let mut captured = Vec::new();
        let mut self_captured = 0;
        if let Move::Play(point) = action {
            let index = point.index(next.size)?;
            if next.cells[index].is_some() {
                return Err(Error::Occupied);
            }
            next.cells[index] = Some(self.to_play);
            for adjacent in next.neighbors(index).collect::<Vec<_>>() {
                if next.cells[adjacent] == Some(self.to_play.opponent()) {
                    let group = next
                        .group_at(Point::from_index(adjacent, next.size))?
                        .expect("occupied point");
                    if group.liberties.is_empty() {
                        for stone in group.stones {
                            next.cells[stone.index(next.size)?] = None;
                            captured.push(stone);
                        }
                    }
                }
            }
            let own_group = next.group_at(point)?.expect("just placed");
            if own_group.liberties.is_empty() {
                if self.rules == Rules::SimpleKoNoSuicide {
                    return Err(Error::Suicide);
                }
                self_captured = own_group.stones.len();
                for stone in own_group.stones {
                    next.cells[stone.index(next.size)?] = None;
                }
            }
            if (self.rules == Rules::SimpleKoNoSuicide
                && self.previous_board.as_ref() == Some(&next))
                || (self.rules == Rules::TrompTaylor
                    && self.positions.iter().any(|b| b.as_ref() == &next))
            {
                return Err(Error::Ko);
            }
        }
        let count = captured.len();
        self.previous_board = Some(std::mem::replace(&mut self.board, next));
        self.captures[self.to_play.index()] += count;
        self.captures[self.to_play.opponent().index()] += self_captured;
        if self.rules == Rules::TrompTaylor && action != Move::Pass {
            self.positions.push(std::sync::Arc::new(self.board.clone()));
        }
        self.history.push(MoveRecord {
            color: self.to_play,
            action,
            captured,
        });
        self.to_play = self.to_play.opponent();
        self.consecutive_passes = if action == Move::Pass {
            self.consecutive_passes + 1
        } else {
            0
        };
        if self.consecutive_passes == 2 {
            self.phase = if self.rules == Rules::TrompTaylor {
                Phase::Finished
            } else {
                Phase::AwaitingScoring
            };
        }
        Ok(count)
    }

    pub fn resume_play(&mut self) -> Result<(), Error> {
        if self.phase != Phase::AwaitingScoring {
            return Err(Error::NotPlaying);
        }
        self.phase = Phase::Playing;
        self.consecutive_passes = 0;
        Ok(())
    }

    pub fn resign(&mut self) -> Result<(), Error> {
        if self.phase != Phase::Playing {
            return Err(Error::NotPlaying);
        }
        self.phase = Phase::Resigned {
            winner: self.to_play.opponent(),
        };
        Ok(())
    }
}
