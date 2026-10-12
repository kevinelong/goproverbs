use crate::{Board, Color, Game, Phase, Rules};

/// Area counts on the current board. No automatic dead-stone removal.
#[derive(Clone, Debug, PartialEq)]
pub struct AreaScore {
    pub black: usize,
    pub white: usize,
    pub neutral: usize,
    pub komi: f64,
}

impl AreaScore {
    pub fn black_margin(&self) -> f64 {
        self.black as f64 - self.white as f64 - self.komi
    }
    pub fn result(&self) -> String {
        let margin = self.black_margin();
        if margin == 0.0 {
            "0".into()
        } else {
            format!("{}+{}", if margin > 0.0 { "B" } else { "W" }, margin.abs())
        }
    }
}

impl Board {
    pub fn area_score(&self, komi: f64) -> AreaScore {
        let mut score = AreaScore {
            black: 0,
            white: 0,
            neutral: 0,
            komi,
        };
        let size = self.size();
        let mut seen = vec![false; size.area()];
        for index in 0..size.area() {
            let p = crate::Point::from_index(index, size);
            match self.at(p).unwrap() {
                Some(Color::Black) => score.black += 1,
                Some(Color::White) => score.white += 1,
                None if !seen[index] => {
                    seen[index] = true;
                    let mut stack = vec![index];
                    let mut count = 0;
                    let mut borders = [false; 2];
                    while let Some(i) = stack.pop() {
                        count += 1;
                        for n in self.neighbors(i) {
                            match self.at(crate::Point::from_index(n, size)).unwrap() {
                                Some(c) => borders[c.index()] = true,
                                None if !seen[n] => {
                                    seen[n] = true;
                                    stack.push(n);
                                }
                                _ => {}
                            }
                        }
                    }
                    match borders {
                        [true, false] => score.black += count,
                        [false, true] => score.white += count,
                        _ => score.neutral += count,
                    }
                }
                None => {}
            }
        }
        score
    }
}

impl Game {
    pub fn final_result(&self) -> Option<String> {
        match self.phase() {
            Phase::Resigned { winner } => Some(format!(
                "{}+R",
                if winner == Color::Black { "B" } else { "W" }
            )),
            Phase::Finished if self.rules() == Rules::TrompTaylor => {
                Some(self.board().area_score(self.komi()).result())
            }
            _ => None,
        }
    }
}
