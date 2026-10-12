use crate::Error;

pub(crate) const COLUMNS: &[u8] = b"ABCDEFGHJKLMNOPQRSTUVWXYZ";

/// Square board size, limited to the GTP coordinate range (2..=25).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BoardSize(u8);

impl BoardSize {
    pub fn new(size: u8) -> Result<Self, Error> {
        if (2..=25).contains(&size) {
            Ok(Self(size))
        } else {
            Err(Error::InvalidSize)
        }
    }

    pub fn get(self) -> u8 {
        self.0
    }

    pub(crate) fn area(self) -> usize {
        usize::from(self.0).pow(2)
    }
}

impl Default for BoardSize {
    fn default() -> Self {
        Self(19)
    }
}

/// Zero-based column and row, with the origin at the upper left (like SGF).
/// A point is checked again when used on a possibly different board.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Point {
    col: u8,
    row: u8,
}

impl Point {
    pub fn new(col: u8, row: u8, size: BoardSize) -> Result<Self, Error> {
        let point = Self { col, row };
        point.index(size)?;
        Ok(point)
    }

    pub fn col(self) -> u8 {
        self.col
    }
    pub fn row(self) -> u8 {
        self.row
    }

    pub(crate) fn index(self, size: BoardSize) -> Result<usize, Error> {
        if self.col >= size.0 || self.row >= size.0 {
            return Err(Error::OutOfBounds);
        }
        Ok(usize::from(self.row) * usize::from(size.0) + usize::from(self.col))
    }

    pub(crate) fn from_index(index: usize, size: BoardSize) -> Self {
        Self {
            col: (index % usize::from(size.0)) as u8,
            row: (index / usize::from(size.0)) as u8,
        }
    }

    pub fn from_gtp(text: &str, size: BoardSize) -> Result<Self, Error> {
        let bytes = text.as_bytes();
        if bytes.len() < 2 || !bytes[1..].iter().all(u8::is_ascii_digit) {
            return Err(Error::InvalidCoordinate);
        }
        let col = COLUMNS
            .iter()
            .position(|&c| c == bytes[0].to_ascii_uppercase())
            .ok_or(Error::InvalidCoordinate)? as u8;
        let number: u8 = text[1..].parse().map_err(|_| Error::InvalidCoordinate)?;
        if number == 0 || number > size.0 {
            return Err(Error::OutOfBounds);
        }
        Self::new(col, size.0 - number, size)
    }

    pub fn to_gtp(self, size: BoardSize) -> Result<String, Error> {
        self.index(size)?;
        Ok(format!(
            "{}{}",
            COLUMNS[usize::from(self.col)] as char,
            size.0 - self.row
        ))
    }

    pub fn from_sgf(text: &str, size: BoardSize) -> Result<Self, Error> {
        let b = text.as_bytes();
        if b.len() != 2 || !b.iter().all(u8::is_ascii_lowercase) {
            return Err(Error::InvalidCoordinate);
        }
        Self::new(b[0] - b'a', b[1] - b'a', size)
    }

    pub fn to_sgf(self, size: BoardSize) -> Result<String, Error> {
        self.index(size)?;
        Ok(format!(
            "{}{}",
            (b'a' + self.col) as char,
            (b'a' + self.row) as char
        ))
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Move {
    Play(Point),
    Pass,
}

impl Move {
    pub fn from_gtp(text: &str, size: BoardSize) -> Result<Self, Error> {
        if text.eq_ignore_ascii_case("pass") {
            Ok(Self::Pass)
        } else {
            Point::from_gtp(text, size).map(Self::Play)
        }
    }

    /// FF[4] uses an empty value for pass; legacy "tt" is pass only up to 19x19.
    pub fn from_sgf(text: &str, size: BoardSize) -> Result<Self, Error> {
        if text.is_empty() || (text == "tt" && size.0 <= 19) {
            Ok(Self::Pass)
        } else {
            Point::from_sgf(text, size).map(Self::Play)
        }
    }

    pub fn to_sgf(self, size: BoardSize) -> Result<String, Error> {
        match self {
            Self::Pass => Ok(String::new()),
            Self::Play(p) => p.to_sgf(size),
        }
    }
}
