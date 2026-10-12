//! An explainable one-ply baseline. Scores are preferences, not points or win rates.
use crate::{Board, Color, Game, Group, Move, Phase, Point};

pub const FEATURES: [&str; 14] = [
    "capture",
    "save_atari",
    "self_atari",
    "connect",
    "fill_eye",
    "empty_corner",
    "side_development",
    "early_33",
    "atari",
    "cut_pressure",
    "stone_balance",
    "atari_risk",
    "liberty_balance",
    "influence_balance",
];

#[derive(Clone, Debug)]
pub struct Weights {
    values: [f64; 14],
}

impl Default for Weights {
    fn default() -> Self {
        Self {
            values: [
                8.0, 10.0, -12.0, 1.5, -15.0, 2.0, 0.5, 0.0, 2.0, 0.0, 1.0, -1.5, 0.1, 0.3,
            ],
        }
    }
}

impl Weights {
    pub fn get(&self, name: &str) -> f64 {
        self.values[FEATURES
            .iter()
            .position(|&f| f == name)
            .expect("known feature")]
    }
    /// Strict, dependency-free profile format: one name=value per line.
    /// Missing entries inherit defaults; duplicates and unknown names fail.
    pub fn from_text(text: &str) -> Result<Self, String> {
        let mut weights = Self::default();
        let mut seen = std::collections::HashSet::new();
        for (line, input) in text.lines().enumerate() {
            let input = input.split('#').next().unwrap().trim();
            if input.is_empty() {
                continue;
            }
            let (name, value) = input
                .split_once('=')
                .ok_or_else(|| format!("line {}: expected name=value", line + 1))?;
            let name = name.trim();
            if !seen.insert(name) {
                return Err(format!("duplicate weight: {name}"));
            }
            weights.set(
                name,
                value
                    .trim()
                    .parse()
                    .map_err(|_| format!("invalid weight: {name}"))?,
            )?;
        }
        Ok(weights)
    }
    pub fn to_text(&self) -> String {
        self.entries()
            .map(|(name, value)| format!("{name}={value}\n"))
            .collect()
    }
    pub fn set(&mut self, name: &str, weight: f64) -> Result<(), String> {
        let i = FEATURES
            .iter()
            .position(|&f| f == name)
            .ok_or("unknown feature")?;
        if !weight.is_finite() || weight.abs() > 1000.0 {
            return Err("weight must be finite and between -1000 and 1000".into());
        }
        self.values[i] = weight;
        Ok(())
    }
    pub fn entries(&self) -> impl Iterator<Item = (&'static str, f64)> + '_ {
        FEATURES.into_iter().zip(self.values)
    }
}

#[derive(Clone, Debug)]
pub struct Contribution {
    pub feature: &'static str,
    pub value: f64,
    pub weight: f64,
    pub score: f64,
}

#[derive(Clone, Debug)]
pub struct Candidate {
    pub action: Move,
    pub score: f64,
    pub contributions: Vec<Contribution>,
}

pub(crate) fn points(board: &Board) -> impl Iterator<Item = Point> {
    let size = board.size();
    (0..size.get())
        .flat_map(move |row| (0..size.get()).map(move |col| Point::new(col, row, size).unwrap()))
}

pub(crate) fn groups(board: &Board, color: Color) -> Vec<Group> {
    let mut seen = std::collections::HashSet::new();
    let mut result = Vec::new();
    for p in points(board) {
        if !seen.contains(&p) && board.at(p).unwrap() == Some(color) {
            let group = board.group_at(p).unwrap().unwrap();
            seen.extend(group.stones.iter().copied());
            result.push(group);
        }
    }
    result
}

fn near(a: Point, b: Point) -> bool {
    a.col().abs_diff(b.col()) + a.row().abs_diff(b.row()) == 1
}

/// Conservative single-point eye shape, not a life-and-death proof.
fn eye_shape(board: &Board, p: Point, color: Color) -> bool {
    let n = i16::from(board.size().get());
    let mut diagonals = 0;
    let mut friendly_diagonals = 0;
    for dy in -1i16..=1 {
        for dx in -1i16..=1 {
            if dx == 0 && dy == 0 {
                continue;
            }
            let x = i16::from(p.col()) + dx;
            let y = i16::from(p.row()) + dy;
            if x < 0 || y < 0 || x >= n || y >= n {
                continue;
            }
            let friendly = board
                .at(Point::new(x as u8, y as u8, board.size()).unwrap())
                .unwrap()
                == Some(color);
            if dx == 0 || dy == 0 {
                if !friendly {
                    return false;
                }
            } else {
                diagonals += 1;
                friendly_diagonals += usize::from(friendly);
            }
        }
    }
    friendly_diagonals >= if diagonals == 4 { 3 } else { diagonals }
}

/// Rank all legal moves plus pass without changing the supplied game.
/// Deterministic ties use row-major point order, with pass last.
pub fn rank_moves(game: &Game, color: Color, weights: &Weights) -> Vec<Candidate> {
    rank_until(game, color, weights, None).unwrap()
}

pub(crate) fn rank_until(
    game: &Game,
    color: Color,
    weights: &Weights,
    deadline: Option<std::time::Instant>,
) -> Option<Vec<Candidate>> {
    if matches!(game.phase(), Phase::Resigned { .. } | Phase::Finished) {
        return Some(Vec::new());
    }
    let position = game.for_color(color);
    let board = position.board();
    let own = groups(board, color);
    let enemy = groups(board, color.opponent());
    let occupied: Vec<_> = points(board)
        .filter(|&p| board.at(p).unwrap().is_some())
        .collect();
    let n = board.size().get();
    // These whole-board opening proxies were designed for standard 19x19.
    // Small boards remain useful for local mechanics, not transferred fuseki.
    let opening = n == 19 && occupied.len() < usize::from(n).pow(2) / 4;
    let mut candidates = Vec::new();
    for p in points(board) {
        if deadline.is_some_and(|d| std::time::Instant::now() >= d) {
            return None;
        }
        if board.at(p).unwrap().is_some() {
            continue;
        }
        let mut next = position.clone();
        let Ok(captured) = next.play(Move::Play(p)) else {
            continue;
        };
        let resulting_group = next.board().group_at(p).unwrap();
        let rescued = own
            .iter()
            .filter(|g| g.liberties.len() == 1)
            // Without a capture, only filling this group's sole liberty can
            // change its connectivity/liberties. Keep the capture case broad.
            .filter(|g| captured > 0 || g.liberties.contains(&p))
            .filter(|g| {
                next.board()
                    .group_at(g.stones[0])
                    .unwrap()
                    .is_some_and(|after| after.liberties.len() >= 2)
            })
            .map(|g| g.stones.len())
            .sum::<usize>();
        let connected = own
            .iter()
            .filter(|g| g.stones.iter().any(|&s| near(s, p)))
            .count()
            .saturating_sub(1);
        let x = p.col().min(n - 1 - p.col());
        let y = p.row().min(n - 1 - p.row());
        let corner_point = (2..=3).contains(&x) && (2..=3).contains(&y);
        let corner_empty = !occupied.iter().any(|s| {
            let sx = if p.col() < n / 2 {
                s.col()
            } else {
                n - 1 - s.col()
            };
            let sy = if p.row() < n / 2 {
                s.row()
            } else {
                n - 1 - s.row()
            };
            sx <= 4 && sy <= 4
        });
        let star = if n >= 9 {
            Point::new(
                if p.col() < n / 2 { 3 } else { n - 4 },
                if p.row() < n / 2 { 3 } else { n - 4 },
                board.size(),
            )
            .ok()
        } else {
            None
        };
        let early_33 = opening
            && x == 2
            && y == 2
            && star.is_some_and(|s| board.at(s).unwrap() == Some(color.opponent()))
            && occupied
                .iter()
                .filter(|s| s.col().abs_diff(p.col()) <= 3 && s.row().abs_diff(p.row()) <= 3)
                .count()
                == 1;
        let raw = [
            (captured as f64 / 4.0).min(1.0),
            (rescued as f64 / 4.0).min(1.0),
            f64::from(
                resulting_group
                    .as_ref()
                    .is_none_or(|g| g.liberties.len() == 1)
                    && captured == 0,
            ),
            (connected as f64 / 3.0).min(1.0),
            f64::from(eye_shape(board, p, color)),
            f64::from(opening && corner_point && corner_empty),
            f64::from(
                opening
                    && !corner_point
                    && (2..=3).contains(&x.min(y))
                    && !occupied
                        .iter()
                        .any(|s| s.col().abs_diff(p.col()) + s.row().abs_diff(p.row()) <= 2),
            ),
            f64::from(early_33),
            (enemy
                .iter()
                // One placement can remove at most one liberty of a surviving
                // enemy chain. Captures and own suicide only add empty points.
                .filter(|g| g.liberties.len() == 2 && g.liberties.contains(&p))
                .filter(|g| {
                    next.board()
                        .group_at(g.stones[0])
                        .unwrap()
                        .is_some_and(|after| after.liberties.len() == 1)
                })
                .map(|g| g.stones.len())
                .sum::<usize>() as f64
                / 4.0)
                .min(1.0),
            (enemy
                .iter()
                .filter(|g| g.stones.iter().any(|&s| near(s, p)))
                .count()
                .saturating_sub(1) as f64
                / 3.0)
                .min(1.0),
        ];
        let contributions: Vec<_> = weights
            .entries()
            .zip(raw)
            .filter(|(_, value)| *value != 0.0)
            .map(|((feature, weight), value)| Contribution {
                feature,
                value,
                weight,
                score: value * weight,
            })
            .collect();
        let score = 0.01 + contributions.iter().map(|c| c.score).sum::<f64>();
        candidates.push(Candidate {
            action: Move::Play(p),
            score,
            contributions,
        });
    }
    candidates.push(Candidate {
        action: Move::Pass,
        score: 0.0,
        contributions: Vec::new(),
    });
    candidates.sort_by(|a, b| b.score.total_cmp(&a.score));
    Some(candidates)
}

pub fn explain(candidate: &Candidate, game: &Game) -> String {
    let vertex = match candidate.action {
        Move::Pass => "pass".into(),
        Move::Play(p) => p.to_gtp(game.board().size()).unwrap(),
    };
    let mut out = format!("{vertex}: {:.3}", candidate.score);
    if candidate.action != Move::Pass {
        out.push_str(" (base=0.010)");
    }
    for term in &candidate.contributions {
        out.push_str(&format!(
            "\n  {}: {:.3} * {:.3} = {:+.3}",
            term.feature, term.value, term.weight, term.score
        ));
    }
    out
}
