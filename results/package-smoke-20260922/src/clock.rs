//! Conservative GTP Canadian/absolute time allocation. Controller is authoritative.
use crate::Color;

#[derive(Clone, Copy, Default)]
struct Remaining {
    millis: u64,
    stones: u32,
    in_period: bool,
}

#[derive(Default)]
pub struct TimeControl {
    remaining: [Option<Remaining>; 2],
    period_millis: u64,
    period_stones: u32,
    unlimited: bool,
}

impl TimeControl {
    pub fn configure(&mut self, main: u32, period: u32, stones: u32) {
        self.period_millis = u64::from(period) * 1000;
        self.period_stones = stones;
        self.unlimited = period > 0 && stones == 0;
        let remaining = if main == 0 && period > 0 && stones > 0 {
            Remaining {
                millis: self.period_millis,
                stones,
                in_period: true,
            }
        } else {
            Remaining {
                millis: u64::from(main) * 1000,
                stones: 0,
                in_period: false,
            }
        };
        self.remaining = if self.unlimited {
            [None; 2]
        } else {
            [Some(remaining); 2]
        };
    }

    pub fn update(&mut self, color: Color, seconds: u32, stones: u32) {
        if !self.unlimited {
            self.remaining[color.index()] = Some(Remaining {
                millis: u64::from(seconds) * 1000,
                stones,
                in_period: stones > 0,
            });
        }
    }

    pub fn budget(&self, color: Color, configured: u64) -> u64 {
        let Some(left) = self.remaining[color.index()] else {
            return configured;
        };
        // Main-time horizon is a simple allocation assumption, not an estimate
        // of territory or actual remaining game length. Keep a small reserve.
        let divisor = if left.in_period {
            u64::from(left.stones.max(1))
        } else {
            30
        };
        configured.min((left.millis / divisor).saturating_sub(10))
    }

    pub fn charge(&mut self, color: Color, elapsed_ms: u64) {
        let Some(left) = self.remaining[color.index()].as_mut() else {
            return;
        };
        if !left.in_period {
            if elapsed_ms >= left.millis && self.period_millis > 0 && self.period_stones > 0 {
                let overtime = elapsed_ms - left.millis;
                left.millis = self.period_millis.saturating_sub(overtime);
                left.stones = self.period_stones;
                left.in_period = true;
                // The move that uses the last main time also consumes a move
                // of the newly entered period only when overtime was spent.
                if overtime > 0 {
                    left.stones = left.stones.saturating_sub(1);
                    if left.stones == 0 && left.millis > 0 {
                        left.millis = self.period_millis;
                        left.stones = self.period_stones;
                    }
                }
            } else {
                left.millis = left.millis.saturating_sub(elapsed_ms);
            }
        } else {
            left.millis = left.millis.saturating_sub(elapsed_ms);
            left.stones = left.stones.saturating_sub(1);
            if left.stones == 0 && left.millis > 0 {
                left.millis = self.period_millis;
                left.stones = self.period_stones;
            }
        }
    }
}
