//! GTP v2 core commands, with private `gp-` extensions for explanations.
use crate::engine::{self, Weights};
use crate::search::{self, Limits};
use crate::{BoardSize, Color, Game, Move};
use std::io::{self, BufRead, Write};

const COMMANDS: &[&str] = &[
    "protocol_version",
    "name",
    "version",
    "known_command",
    "list_commands",
    "quit",
    "boardsize",
    "clear_board",
    "komi",
    "play",
    "genmove",
    "showboard",
    "undo",
    "gp-explain",
    "gp-weights",
    "gp-weight",
    "gp-sgf",
    "gp-search",
    "gp-last-search",
    "gp-limits",
    "gp-tactical",
    "gp-mode",
    "gp-shortlist",
    "gp-load-weights",
    "gp-save-weights",
    "gp-candidates",
    "final_score",
];

#[derive(Default)]
pub struct Engine {
    game: Game,
    weights: Weights,
    undo: Vec<Game>,
    limits: Limits,
    last_search: Option<String>,
}

pub struct Response {
    pub text: String,
    pub quit: bool,
}

impl Engine {
    pub fn configured(game: Game, weights: Weights, limits: Limits) -> Self {
        Self {
            game,
            weights,
            limits,
            undo: Vec::new(),
            last_search: None,
        }
    }
    pub fn game(&self) -> &Game {
        &self.game
    }

    /// Exactly one response per nonempty command, ending in two newlines.
    pub fn handle_line(&mut self, line: &str) -> Option<Response> {
        let clean: String = line
            .chars()
            .filter(|c| !c.is_control() || *c == '\t')
            .collect();
        let mut words: Vec<&str> = clean
            .split('#')
            .next()
            .unwrap_or("")
            .split_whitespace()
            .collect();
        if words.is_empty() {
            return None;
        }
        let mut id = "";
        if words[0].bytes().all(|b| b.is_ascii_digit()) {
            id = words.remove(0);
            if id.parse::<u32>().is_err() || id.parse::<u32>().unwrap() > i32::MAX as u32 {
                return Some(Response {
                    text: "? invalid command id\n\n".into(),
                    quit: false,
                });
            }
        }
        let command = words.first().copied().unwrap_or("");
        let args = words.get(1..).unwrap_or(&[]);
        let result = self.execute(command, args);
        let quit = command == "quit" && result.is_ok();
        let text = match result {
            Ok(payload) if payload.is_empty() => format!("={id}\n\n"),
            Ok(payload) => format!("={id} {}\n\n", payload.trim_end_matches('\n')),
            Err(error) => format!("?{id} {error}\n\n"),
        };
        Some(Response { text, quit })
    }

    fn execute(&mut self, command: &str, args: &[&str]) -> Result<String, String> {
        if !COMMANDS.contains(&command) {
            return Err("unknown command".into());
        }
        let arity = match command {
            "known_command" | "boardsize" | "komi" | "genmove" | "gp-search"
            | "gp-load-weights" | "gp-save-weights" | "gp-candidates" | "gp-tactical"
            | "gp-mode" | "gp-shortlist" => 1,
            "play" | "gp-explain" | "gp-weight" => 2,
            "gp-limits" => 4,
            _ => 0,
        };
        if args.len() != arity {
            return Err("syntax error".into());
        }
        match command {
            "protocol_version" => Ok("2".into()),
            "name" => Ok("goproverbs".into()),
            "version" => Ok(env!("CARGO_PKG_VERSION").into()),
            "known_command" => Ok(COMMANDS.contains(&args[0]).to_string()),
            "list_commands" => Ok(COMMANDS.join("\n")),
            "quit" => Ok(String::new()),
            "boardsize" => {
                let n = args[0].parse::<u8>().map_err(|_| "unacceptable size")?;
                let size = BoardSize::new(n).map_err(|_| "unacceptable size")?;
                self.game = Game::with_rules(size, self.game.komi(), self.game.rules()).unwrap();
                self.undo.clear();
                self.last_search = None;
                Ok(String::new())
            }
            "clear_board" => {
                self.game = Game::with_rules(
                    self.game.board().size(),
                    self.game.komi(),
                    self.game.rules(),
                )
                .unwrap();
                self.undo.clear();
                self.last_search = None;
                Ok(String::new())
            }
            "komi" => {
                let value = args[0].parse().map_err(|_| "syntax error")?;
                self.game.set_komi(value).map_err(|e| e.to_string())?;
                Ok(String::new())
            }
            "play" => {
                let color = color(args[0])?;
                let action = Move::from_gtp(args[1], self.game.board().size())
                    .map_err(|_| "illegal move")?;
                self.apply(color, action)?;
                Ok(String::new())
            }
            "genmove" => {
                let color = color(args[0])?;
                if self.game.final_result().is_some() {
                    return Ok("pass".into());
                }
                let analysis = search::analyze(&self.game, color, &self.weights, self.limits)?;
                let report = search::explain(&analysis, &self.game);
                let vertex = vertex(analysis.action, &self.game);
                self.apply(color, analysis.action)?;
                self.last_search = Some(report);
                Ok(vertex)
            }
            "showboard" => Ok(format!("\n{}", self.game.board().to_ascii())),
            "undo" => {
                let komi = self.game.komi();
                self.game = self.undo.pop().ok_or("cannot undo")?;
                self.game.set_komi(komi).unwrap();
                self.last_search = None;
                Ok(String::new())
            }
            "gp-explain" => {
                let color = color(args[0])?;
                let action =
                    Move::from_gtp(args[1], self.game.board().size()).map_err(|e| e.to_string())?;
                let candidates = engine::rank_moves(&self.game, color, &self.weights);
                let candidate = candidates
                    .iter()
                    .find(|c| c.action == action)
                    .ok_or("illegal move")?;
                Ok(engine::explain(candidate, &self.game))
            }
            "gp-weights" => Ok(self
                .weights
                .entries()
                .map(|(name, weight)| format!("{name} {weight}"))
                .collect::<Vec<_>>()
                .join("\n")),
            "gp-weight" => {
                let weight = args[1].parse().map_err(|_| "invalid weight")?;
                self.weights.set(args[0], weight)?;
                Ok(String::new())
            }
            "gp-sgf" => Ok(self.game.to_sgf()),
            "final_score" => self.game.final_result().ok_or_else(|| {
                "score unavailable: finish a Tromp-Taylor game with two passes".into()
            }),
            "gp-search" => {
                let analysis =
                    search::analyze(&self.game, color(args[0])?, &self.weights, self.limits)?;
                Ok(search::explain(&analysis, &self.game))
            }
            "gp-last-search" => self
                .last_search
                .clone()
                .ok_or_else(|| "no generated move to explain".into()),
            "gp-limits" => {
                let limits = Limits {
                    time_ms: args[0].parse().map_err(|_| "invalid milliseconds")?,
                    max_nodes: args[1].parse().map_err(|_| "invalid node limit")?,
                    max_depth: args[2].parse().map_err(|_| "invalid depth")?,
                    beam: args[3].parse().map_err(|_| "invalid beam")?,
                    tactical_plies: self.limits.tactical_plies,
                    ..self.limits
                };
                limits.validate()?;
                self.limits = limits;
                Ok(String::new())
            }
            "gp-tactical" => {
                let limits = Limits {
                    tactical_plies: args[0].parse().map_err(|_| "invalid tactical plies")?,
                    ..self.limits
                };
                limits.validate()?;
                self.limits = limits;
                Ok(String::new())
            }
            "gp-mode" => {
                self.limits.mode = args[0].parse()?;
                Ok(String::new())
            }
            "gp-shortlist" => {
                let limits = Limits {
                    shortlist: args[0].parse().map_err(|_| "invalid shortlist")?,
                    ..self.limits
                };
                limits.validate()?;
                self.limits = limits;
                Ok(String::new())
            }
            "gp-load-weights" => {
                let text = std::fs::read_to_string(args[0]).map_err(|e| e.to_string())?;
                self.weights = Weights::from_text(&text)?;
                Ok(String::new())
            }
            "gp-save-weights" => {
                std::fs::write(args[0], self.weights.to_text()).map_err(|e| e.to_string())?;
                Ok(String::new())
            }
            "gp-candidates" => Ok(
                engine::rank_moves(&self.game, color(args[0])?, &self.weights)
                    .iter()
                    .map(|c| {
                        format!(
                            "{} {:.8} {}",
                            vertex(c.action, &self.game),
                            c.score,
                            c.contributions
                                .iter()
                                .map(|t| format!("{}:{:.8}", t.feature, t.value))
                                .collect::<Vec<_>>()
                                .join(" ")
                        )
                    })
                    .collect::<Vec<_>>()
                    .join("\n"),
            ),
            _ => unreachable!(),
        }
    }

    fn apply(&mut self, color: Color, action: Move) -> Result<(), String> {
        let before = self.game.clone();
        self.game
            .play_as(color, action)
            .map_err(|_| "illegal move")?;
        self.undo.push(before);
        self.last_search = None;
        Ok(())
    }
}

fn color(text: &str) -> Result<Color, String> {
    match text.to_ascii_lowercase().as_str() {
        "b" | "black" => Ok(Color::Black),
        "w" | "white" => Ok(Color::White),
        _ => Err("invalid color".into()),
    }
}

fn vertex(action: Move, game: &Game) -> String {
    match action {
        Move::Pass => "pass".into(),
        Move::Play(p) => p.to_gtp(game.board().size()).unwrap(),
    }
}

pub fn serve(input: impl BufRead, mut output: impl Write) -> io::Result<()> {
    let mut engine = Engine::default();
    serve_engine(input, &mut output, &mut engine)
}

pub fn serve_engine(
    input: impl BufRead,
    mut output: impl Write,
    engine: &mut Engine,
) -> io::Result<()> {
    for line in input.lines() {
        if let Some(response) = engine.handle_line(&line?) {
            output.write_all(response.text.as_bytes())?;
            output.flush()?;
            if response.quit {
                break;
            }
        }
    }
    Ok(())
}
