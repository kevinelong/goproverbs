//! Selective negamax with alpha-beta pruning and completed-iteration fallback.
//! This is bounded tactical reading, not a proof that a move or group is safe.
use crate::engine::{self, Candidate, Weights};
use crate::{Color, Game, Move, Phase};
use std::time::{Duration, Instant};

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Mode {
    #[default]
    Selective,
    Full,
    Minimax,
    Hybrid,
}
impl Mode {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Selective => "selective",
            Self::Full => "full",
            Self::Minimax => "minimax",
            Self::Hybrid => "hybrid",
        }
    }
}
impl std::str::FromStr for Mode {
    type Err = String;
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "selective" => Ok(Self::Selective),
            "full" => Ok(Self::Full),
            "minimax" => Ok(Self::Minimax),
            "hybrid" => Ok(Self::Hybrid),
            _ => Err("search mode must be selective, full, minimax, or hybrid".into()),
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct Limits {
    pub time_ms: u64,
    pub max_nodes: usize,
    pub max_depth: u8,
    pub beam: usize,
    /// Extra plies only while a leaf contains a group in atari; zero disables.
    pub tactical_plies: u8,
    pub mode: Mode,
    /// Hybrid nominees from each of the heuristic and shallow-search rankings.
    pub shortlist: usize,
}
impl Default for Limits {
    fn default() -> Self {
        Self {
            time_ms: 1000,
            max_nodes: 20_000,
            max_depth: 4,
            beam: 12,
            tactical_plies: 0,
            mode: Mode::Selective,
            shortlist: 3,
        }
    }
}
impl Limits {
    pub fn validate(&self) -> Result<(), String> {
        if self.time_ms > 3_600_000
            || self.max_nodes == 0
            || self.max_nodes > 10_000_000
            || self.max_depth == 0
            || self.max_depth > 12
            || self.beam == 0
            || self.beam > 625
            || self.tactical_plies > 4
            || self.shortlist == 0
            || self.shortlist > 625
        {
            Err("limits: ms 0..3600000, nodes 1..10000000, depth 1..12, beam 1..625, tactical plies 0..4, shortlist 1..625".into())
        } else {
            Ok(())
        }
    }
}

#[derive(Clone, Debug)]
pub struct RootEvidence {
    pub action: Move,
    pub heuristic: f64,
    pub scout: Option<f64>,
    pub verified: Option<f64>,
    pub depth: u8,
    pub nominated: bool,
}

#[derive(Clone, Debug)]
pub struct Analysis {
    pub mode: Mode,
    pub action: Move,
    pub score: f64,
    pub depth: u8,
    pub nodes: usize,
    pub tactical_nodes: usize,
    pub elapsed_ms: u128,
    pub limited: bool,
    pub principal_variation: Vec<Move>,
    pub policy: Option<Candidate>,
    pub root_candidates: usize,
    pub root_searched: usize,
    pub leaf_terms: Vec<engine::Contribution>,
    pub path_preference: f64,
    pub root_evidence: Vec<RootEvidence>,
}

struct Reader<'a> {
    weights: &'a Weights,
    limits: Limits,
    deadline: Instant,
    nodes: usize,
    tactical_nodes: usize,
}

/// Positional terms are deliberately exposed independently of move preferences.
pub fn evaluate(game: &Game, color: Color, weights: &Weights) -> f64 {
    evaluation_terms(game, color, weights)
        .iter()
        .map(|t| t.score)
        .sum()
}

/// Signed feature totals from one player's perspective, also used in explanations.
pub fn evaluation_terms(game: &Game, color: Color, weights: &Weights) -> Vec<engine::Contribution> {
    let term = |feature, value, weight| engine::Contribution {
        feature,
        value,
        weight,
        score: value * weight,
    };
    if game.phase() == Phase::Finished {
        let margin = game.board().area_score(game.komi()).black_margin();
        let value = if color == Color::Black {
            margin
        } else {
            -margin
        };
        return vec![term("terminal_area_margin", value, 1.0)];
    }
    let komi = if color == Color::Black {
        -game.komi()
    } else {
        game.komi()
    };
    let (mut stones, mut atari, mut liberties, mut influence) = (0.0, 0.0, 0.0, 0.0);
    for c in [color, color.opponent()] {
        let sign = if c == color { 1.0 } else { -1.0 };
        for group in engine::groups(game.board(), c) {
            stones += sign * group.stones.len() as f64;
            if group.liberties.len() == 1 {
                atari += sign * group.stones.len() as f64;
            }
            liberties += sign * group.liberties.len().min(6) as f64;
        }
    }
    // Limited-radius nearest-stone influence; does not label remote empty board
    // as territory just because only one color has played yet.
    let occupied: Vec<_> = engine::points(game.board())
        .filter_map(|p| game.board().at(p).unwrap().map(|c| (p, c)))
        .collect();
    for p in engine::points(game.board()).filter(|&p| game.board().at(p).unwrap().is_none()) {
        let mut distances = [5u8; 2];
        for &(s, c) in &occupied {
            distances[c.index()] =
                distances[c.index()].min(p.col().abs_diff(s.col()) + p.row().abs_diff(s.row()));
        }
        let own = distances[color.index()];
        let opponent = distances[color.opponent().index()];
        if own < opponent {
            influence += 1.0 / f64::from(own);
        } else if opponent < own {
            influence -= 1.0 / f64::from(opponent);
        }
    }
    vec![
        term("komi", komi, 1.0),
        term("stone_balance", stones, weights.get("stone_balance")),
        term("atari_risk", atari, weights.get("atari_risk")),
        term("liberty_balance", liberties, weights.get("liberty_balance")),
        term(
            "influence_balance",
            influence,
            weights.get("influence_balance"),
        ),
    ]
}

fn select(candidates: &[Candidate], beam: usize) -> Vec<&Candidate> {
    // Preserve immediate captures, rescues and new ataris beyond the quiet beam.
    // These are still only short tactical indicators, not forced-win proofs.
    candidates
        .iter()
        .enumerate()
        .filter(|(i, c)| {
            *i < beam
                || c.action == Move::Pass
                || c.contributions.iter().any(|t| {
                    matches!(t.feature, "capture" | "save_atari" | "atari") && t.value > 0.0
                })
        })
        .map(|(_, c)| c)
        .collect()
}

fn hybrid_roots<'a>(
    candidates: &'a [Candidate],
    evidence: &[RootEvidence],
    width: usize,
) -> Vec<&'a Candidate> {
    let mut scout_order: Vec<_> = (0..candidates.len()).collect();
    scout_order.sort_by(|&a, &b| {
        evidence[b]
            .scout
            .unwrap()
            .total_cmp(&evidence[a].scout.unwrap())
    });
    candidates
        .iter()
        .enumerate()
        .filter(|(i, c)| {
            *i < width
                || scout_order.iter().take(width).any(|j| j == i)
                || c.action == Move::Pass
                || c.contributions.iter().any(|t| {
                    matches!(t.feature, "capture" | "save_atari" | "atari") && t.value > 0.0
                })
        })
        .map(|(_, c)| c)
        .collect()
}

impl Reader<'_> {
    fn expired(&self) -> bool {
        self.nodes >= self.limits.max_nodes || Instant::now() >= self.deadline
    }

    fn negamax(
        &mut self,
        game: &Game,
        depth: u8,
        tactical_left: u8,
        mut alpha: f64,
        beta: f64,
    ) -> Option<(f64, Vec<Move>)> {
        if self.expired() {
            return None;
        }
        self.nodes += 1;
        let terminal = matches!(game.phase(), Phase::Finished | Phase::AwaitingScoring);
        let extend = depth == 0
            && tactical_left > 0
            && !terminal
            && [Color::Black, Color::White].into_iter().any(|c| {
                engine::groups(game.board(), c)
                    .iter()
                    .any(|g| g.liberties.len() == 1)
            });
        if terminal || (depth == 0 && !extend) {
            return Some((evaluate(game, game.to_play(), self.weights), Vec::new()));
        }
        if extend {
            self.tactical_nodes += 1;
        }
        let candidates =
            engine::rank_until(game, game.to_play(), self.weights, Some(self.deadline))?;
        let mut best = (f64::NEG_INFINITY, Vec::new());
        // At extended leaves, keep one non-tactical alternative as well as
        // captures/rescues/new ataris and a real pass. No virtual stand-pat turn.
        let selected = if extend {
            let quiet = candidates.iter().position(|c| {
                c.action != Move::Pass
                    && !c.contributions.iter().any(|t| {
                        matches!(t.feature, "capture" | "save_atari" | "atari") && t.value > 0.0
                    })
            });
            candidates
                .iter()
                .enumerate()
                .filter(|(i, c)| {
                    Some(*i) == quiet
                        || c.action == Move::Pass
                        || c.contributions.iter().any(|t| {
                            matches!(t.feature, "capture" | "save_atari" | "atari") && t.value > 0.0
                        })
                })
                .map(|(_, c)| c)
                .collect()
        } else if matches!(self.limits.mode, Mode::Full | Mode::Minimax) {
            candidates.iter().collect()
        } else {
            select(&candidates, self.limits.beam)
        };
        for candidate in selected {
            if self.expired() {
                return None;
            }
            let mut next = game.clone();
            next.play(candidate.action).ok()?;
            let bonus = 0.15 * candidate.score.clamp(-20.0, 20.0);
            let (child, pv) = self.negamax(
                &next,
                depth.saturating_sub(1),
                if extend {
                    tactical_left - 1
                } else {
                    tactical_left
                },
                bonus - beta,
                bonus - alpha,
            )?;
            let value = bonus - child;
            if value > best.0 {
                best = (value, std::iter::once(candidate.action).chain(pv).collect());
            }
            alpha = alpha.max(value);
            if self.limits.mode != Mode::Minimax && alpha >= beta {
                break;
            }
        }
        Some(best)
    }
}

pub fn analyze(
    game: &Game,
    color: Color,
    weights: &Weights,
    limits: Limits,
) -> Result<Analysis, String> {
    limits.validate()?;
    if matches!(game.phase(), Phase::Finished | Phase::Resigned { .. }) {
        return Err("game has ended".into());
    }
    let start = Instant::now();
    let deadline = start + Duration::from_millis(limits.time_ms);
    let position = game.for_color(color);
    // A bounded legal fallback exists even when the caller requests zero time.
    let fallback = engine::points(position.board())
        .find_map(|p| {
            let action = Move::Play(p);
            position.clone().play(action).ok().map(|_| action)
        })
        .unwrap_or(Move::Pass);
    let mut result = Analysis {
        mode: limits.mode,
        action: fallback,
        score: evaluate(&position, color, weights),
        depth: 0,
        nodes: 0,
        tactical_nodes: 0,
        elapsed_ms: 0,
        limited: false,
        principal_variation: vec![fallback],
        policy: None,
        root_candidates: 0,
        root_searched: 0,
        leaf_terms: Vec::new(),
        path_preference: 0.0,
        root_evidence: Vec::new(),
    };
    let Some(candidates) = engine::rank_until(&position, color, weights, Some(deadline)) else {
        result.limited = true;
        result.elapsed_ms = start.elapsed().as_millis();
        return Ok(result);
    };
    let mut roots = if limits.mode == Mode::Selective {
        select(&candidates, limits.beam)
    } else {
        candidates.iter().collect()
    };
    if limits.mode == Mode::Hybrid {
        result.root_evidence = candidates
            .iter()
            .map(|c| RootEvidence {
                action: c.action,
                heuristic: c.score,
                scout: None,
                verified: None,
                depth: 0,
                nominated: false,
            })
            .collect();
    }
    result.root_candidates = candidates.len();
    result.root_searched = roots.len();
    if let Some(best) = candidates.first() {
        result.action = best.action;
        result.policy = Some(best.clone());
        result.principal_variation = vec![best.action];
    }
    let mut reader = Reader {
        weights,
        limits,
        deadline,
        nodes: 0,
        tactical_nodes: 0,
    };
    for depth in 1..=limits.max_depth {
        let mut best: Option<(f64, Vec<Move>, Candidate)> = None;
        let mut stage_scores = Vec::new();
        let mut complete = true;
        for &candidate in &roots {
            if reader.expired() {
                complete = false;
                break;
            }
            let mut next = position.clone();
            next.play(candidate.action).map_err(|e| e.to_string())?;
            let bonus = 0.15 * candidate.score.clamp(-20.0, 20.0);
            // Full root windows make reported root scores directly comparable.
            let Some((child, pv)) = reader.negamax(
                &next,
                depth - 1,
                if limits.mode == Mode::Hybrid && depth == 1 {
                    0
                } else {
                    limits.tactical_plies
                },
                f64::NEG_INFINITY,
                f64::INFINITY,
            ) else {
                complete = false;
                break;
            };
            let value = bonus - child;
            stage_scores.push((candidate.action, value));
            if best.as_ref().is_none_or(|b| value > b.0) {
                best = Some((
                    value,
                    std::iter::once(candidate.action).chain(pv).collect(),
                    candidate.clone(),
                ));
            }
        }
        if !complete {
            result.limited = true;
            break;
        }
        if let Some((score, pv, policy)) = best {
            result.action = pv[0];
            result.score = score;
            result.depth = depth;
            result.principal_variation = pv;
            result.policy = Some(policy);
            result.root_searched = stage_scores.len();
        }
        if limits.mode == Mode::Hybrid {
            // Commit only a whole round: never compare a partially verified
            // move with candidates whose scores came from a shallower depth.
            for (action, value) in stage_scores {
                let evidence = result
                    .root_evidence
                    .iter_mut()
                    .find(|e| e.action == action)
                    .unwrap();
                if depth == 1 {
                    evidence.scout = Some(value);
                } else {
                    evidence.verified = Some(value);
                    evidence.depth = depth;
                }
            }
            if depth == 1 {
                roots = hybrid_roots(&candidates, &result.root_evidence, limits.shortlist);
                for evidence in &mut result.root_evidence {
                    evidence.nominated = roots.iter().any(|c| c.action == evidence.action);
                }
            }
        }
    }
    result.nodes = reader.nodes;
    result.tactical_nodes = reader.tactical_nodes;
    if result.depth > 0 {
        let mut leaf = position.clone();
        for &action in &result.principal_variation {
            leaf.play(action).map_err(|e| e.to_string())?;
        }
        result.leaf_terms = evaluation_terms(&leaf, color, weights);
        result.path_preference =
            result.score - result.leaf_terms.iter().map(|t| t.score).sum::<f64>();
    }
    result.elapsed_ms = start.elapsed().as_millis();
    Ok(result)
}

pub fn explain(analysis: &Analysis, game: &Game) -> String {
    let vertex = |m: &Move| match m {
        Move::Pass => "pass".into(),
        Move::Play(p) => p.to_gtp(game.board().size()).unwrap(),
    };
    let mut out = format!(
        "move={} score={:.3} depth={} nodes={} tactical_nodes={} elapsed_ms={} limited={} root_searched={}/{} mode={}\npv={}",
        vertex(&analysis.action),
        analysis.score,
        analysis.depth,
        analysis.nodes,
        analysis.tactical_nodes,
        analysis.elapsed_ms,
        analysis.limited,
        analysis.root_searched,
        analysis.root_candidates,
        analysis.mode.as_str(),
        analysis
            .principal_variation
            .iter()
            .map(vertex)
            .collect::<Vec<_>>()
            .join(" ")
    );
    if analysis.depth == 0 {
        out.push_str("\nNo search iteration completed; score evaluates the current board, not the fallback move.");
    }
    if !analysis.leaf_terms.is_empty() {
        out.push_str("\nLeaf evaluation from the root player's perspective:");
        for t in &analysis.leaf_terms {
            out.push_str(&format!(
                "\n  {}: {:.3} * {:.3} = {:+.3}",
                t.feature, t.value, t.weight, t.score
            ));
        }
        out.push_str(&format!(
            "\nAlternating move preferences along PV: {:+.3}",
            analysis.path_preference
        ));
    }
    if let Some(policy) = &analysis.policy {
        out.push_str(&format!(
            "\nMove preferences (not the search score):\n{}",
            engine::explain(policy, game)
        ));
    }
    if analysis.mode == Mode::Hybrid && !analysis.root_evidence.is_empty() {
        out.push_str("\nHybrid nominees: heuristic preference, one-ply scout, completed deeper verification.");
        for e in analysis.root_evidence.iter().filter(|e| e.nominated) {
            let number =
                |v: Option<f64>| v.map_or_else(|| "unsearched".into(), |v| format!("{v:.3}"));
            out.push_str(&format!(
                "\n  {} heuristic={:.3} scout={} verified={} depth={} selected={}",
                vertex(&e.action),
                e.heuristic,
                number(e.scout),
                number(e.verified),
                e.depth,
                e.action == analysis.action
            ));
        }
        out.push_str("\nVerification is bounded search evidence, not proof. Only equal-depth completed scores decide the move.");
    }
    out
}
