use goproverbs::engine::{self, Weights};
use goproverbs::search::{self, Limits};
use goproverbs::{BoardSize, Game, Move, Rules};
use std::io::{self, Write};

const HELP: &str = "goproverbs - explainable Go player
Usage: goproverbs [OPTIONS] [MOVE ...]
       goproverbs --gtp [--profile FILE] [SEARCH OPTIONS]

--size N                 Board size 2..25 (default 19)
--komi POINTS            White compensation (default 6.5)
--rules tt|simple        Tromp-Taylor (default) or legacy simple ko/no suicide
--suggest                Search and explain a move without playing it
--rank                   Show the top five immediate heuristic preferences
--sgf                    Export the game record
--gtp                    Speak GTP v2 on standard input/output
--profile FILE           Load a name=value weight profile
--weight NAME=VALUE      Override a weight (repeatable, applied in argument order)
--write-profile FILE     Save the resulting profile and exit
--time-ms N              Search time budget (default 1000)
--nodes N                Tree position budget (default 20000)
--depth N                Maximum alternating plies (default 4)
--beam N                 Quiet candidates per position (default 12)
--tactical-plies N       Extra plies at atari leaves, 0..4 (default 0)
--search MODE            selective (default), full, minimax, or hybrid
--shortlist N            Hybrid nominees per ranking (default 3)
-h, --help               Show this help

Moves alternate colors: D4 Q16 pass. Coordinates skip I. Resign is accepted.
Tromp-Taylor uses positional superko, permits legal multi-stone suicide,
and scores the board as it stands after two passes. Capture dead stones first.
Search is selective, CPU-only, and has no established playing-strength rating.";

fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let mut size = BoardSize::default();
    let mut komi = 6.5;
    let mut rules = Rules::TrompTaylor;
    let mut weights = Weights::default();
    let mut limits = Limits::default();
    let mut mode = "board";
    let mut moves = Vec::new();
    let mut save_profile = None;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "-h" | "--help" => return output(&format!("{HELP}\n")),
            "--size" => {
                size = BoardSize::new(
                    args.next()
                        .ok_or("--size requires a number")?
                        .parse()
                        .map_err(|_| "invalid size")?,
                )
                .map_err(|e| e.to_string())?
            }
            "--komi" => {
                komi = args
                    .next()
                    .ok_or("--komi requires a number")?
                    .parse()
                    .map_err(|_| "invalid komi")?
            }
            "--rules" => {
                rules = match args.next().ok_or("--rules requires tt or simple")?.as_str() {
                    "tt" => Rules::TrompTaylor,
                    "simple" => Rules::SimpleKoNoSuicide,
                    _ => return Err("unknown rules; use tt or simple".into()),
                }
            }
            "--gtp" | "--sgf" | "--suggest" | "--rank" => {
                if mode != "board" {
                    return Err("choose one of --gtp, --sgf, --suggest, --rank".into());
                }
                mode = match arg.as_str() {
                    "--gtp" => "gtp",
                    "--sgf" => "sgf",
                    "--suggest" => "suggest",
                    _ => "rank",
                };
            }
            "--profile" => {
                let path = args.next().ok_or("--profile requires a file")?;
                weights = Weights::from_text(
                    &std::fs::read_to_string(&path).map_err(|e| format!("{path}: {e}"))?,
                )?;
            }
            "--write-profile" => {
                save_profile = Some(args.next().ok_or("--write-profile requires a file")?)
            }
            "--weight" => {
                let value = args.next().ok_or("--weight requires NAME=VALUE")?;
                let (name, value) = value
                    .split_once('=')
                    .ok_or("--weight requires NAME=VALUE")?;
                weights.set(name, value.parse().map_err(|_| "invalid weight")?)?;
            }
            "--time-ms" => {
                limits.time_ms = args
                    .next()
                    .ok_or("--time-ms requires a number")?
                    .parse()
                    .map_err(|_| "invalid time")?
            }
            "--nodes" => {
                limits.max_nodes = args
                    .next()
                    .ok_or("--nodes requires a number")?
                    .parse()
                    .map_err(|_| "invalid nodes")?
            }
            "--depth" => {
                limits.max_depth = args
                    .next()
                    .ok_or("--depth requires a number")?
                    .parse()
                    .map_err(|_| "invalid depth")?
            }
            "--beam" => {
                limits.beam = args
                    .next()
                    .ok_or("--beam requires a number")?
                    .parse()
                    .map_err(|_| "invalid beam")?
            }
            "--tactical-plies" => {
                limits.tactical_plies = args
                    .next()
                    .ok_or("--tactical-plies requires a number")?
                    .parse()
                    .map_err(|_| "invalid tactical plies")?;
            }
            "--search" => {
                limits.mode = args.next().ok_or("--search requires a mode")?.parse()?;
            }
            "--shortlist" => {
                limits.shortlist = args
                    .next()
                    .ok_or("--shortlist requires a number")?
                    .parse()
                    .map_err(|_| "invalid shortlist")?;
            }
            _ if arg.starts_with('-') => return Err(format!("unknown option: {arg}")),
            _ => moves.push(arg),
        }
    }
    limits.validate()?;
    let mut game = Game::with_rules(size, komi, rules).map_err(|e| e.to_string())?;
    if let Some(path) = save_profile {
        if mode == "gtp" {
            return Err("--write-profile cannot be combined with --gtp".into());
        }
        std::fs::write(&path, weights.to_text()).map_err(|e| e.to_string())?;
        return output(&format!("Saved weights to {path}\n"));
    }
    if mode == "gtp" {
        if !moves.is_empty() {
            return Err("use GTP play commands instead of positional moves with --gtp".into());
        }
        let mut engine = goproverbs::gtp::Engine::configured(game, weights, limits);
        return goproverbs::gtp::serve_engine(io::stdin().lock(), io::stdout().lock(), &mut engine)
            .map_err(|e| e.to_string());
    }
    for (i, text) in moves.iter().enumerate() {
        let result = if text.eq_ignore_ascii_case("resign") {
            game.resign().map(|_| 0)
        } else {
            Move::from_gtp(text, size).and_then(|m| game.play(m))
        };
        result.map_err(|e| format!("move {} ({text}): {e}", i + 1))?;
    }
    let text = match mode {
        "sgf" => format!("{}\n", game.to_sgf()),
        "suggest" => {
            let analysis = search::analyze(&game, game.to_play(), &weights, limits)?;
            format!(
                "{}\n{}\n",
                game.to_ascii(),
                search::explain(&analysis, &game)
            )
        }
        "rank" => format!(
            "{}\n{}\n",
            game.to_ascii(),
            engine::rank_moves(&game, game.to_play(), &weights)
                .iter()
                .take(5)
                .map(|c| engine::explain(c, &game))
                .collect::<Vec<_>>()
                .join("\n")
        ),
        _ => game.to_ascii(),
    };
    output(&text)
}

fn output(text: &str) -> Result<(), String> {
    match io::stdout().lock().write_all(text.as_bytes()) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == io::ErrorKind::BrokenPipe => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}
fn main() -> std::process::ExitCode {
    match run() {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("error: {e}");
            std::process::ExitCode::FAILURE
        }
    }
}
