//! Bounded SGF FF[4] import, not a general SGF editor or national-rules converter.
use crate::{BoardSize, Color, Game, Move, Phase, Rules};
use std::collections::BTreeMap;

type Node = BTreeMap<String, Vec<String>>;

/// Import the first game and its first variation, preserving move history.
///
/// Requires explicit Tromp-Taylor rules; defaults are FF[4], GM[1], SZ[19],
/// KM[0]. Only square boards (2..=25) and UTF-8 input are supported. Setup,
/// handicap, non-black initial PL, and midgame rule changes are rejected.
/// Annotation properties are ignored, including RE (moves determine phase).
/// `Some(n)` returns the position after the first n moves, or the final position
/// if n exceeds the move count. Zero returns the empty initial position.
/// The entire selected mainline is still checked for legal moves, even after
/// the limit. All other games/variations are checked for syntax only.
pub fn parse(input: &str, move_limit: Option<usize>) -> Result<Game, String> {
    if input.len() > 8 * 1024 * 1024 {
        return Err("SGF exceeds the 8 MiB import limit".into());
    }
    let mut parser = Parser { input, offset: 0 };
    if parser.peek() == Some('\u{feff}') {
        parser.bump();
    }
    parser.space();
    let mut nodes = Vec::new();
    parser.tree(0, true, &mut nodes)?;
    parser.space();
    while parser.peek().is_some() {
        parser.tree(0, false, &mut nodes)?;
        parser.space();
    }
    let root = &nodes[0];
    if single(root, "FF", "4")?.trim() != "4" {
        return Err("only SGF FF[4] import is supported".into());
    }
    if single(root, "GM", "1")?.trim() != "1" {
        return Err("only Go SGF (GM[1]) is supported".into());
    }
    if !single(root, "CA", "UTF-8")?
        .trim()
        .eq_ignore_ascii_case("UTF-8")
    {
        return Err("only UTF-8 SGF input is supported".into());
    }
    let rules = single(root, "RU", "")?.trim().to_ascii_lowercase();
    if !matches!(rules.as_str(), "tromp-taylor" | "tromp taylor" | "tt") {
        return Err("explicit RU[Tromp-Taylor] is required; rule conversion is unsupported".into());
    }
    if single(root, "PL", "B")?.trim() != "B" {
        return Err("only the default initial player PL[B] is supported".into());
    }
    let size_text = single(root, "SZ", "19")?.trim();
    let mut sides = size_text.split(':');
    let first = sides.next().unwrap_or_default();
    let size_number = first.parse::<u8>().map_err(|_| "invalid SGF board size")?;
    if let Some(second) = sides.next()
        && (second.parse::<u8>().ok() != Some(size_number) || sides.next().is_some())
    {
        return Err("only square SGF boards are supported".into());
    }
    let size = BoardSize::new(size_number).map_err(|e| e.to_string())?;
    let komi = single(root, "KM", "0")?
        .trim()
        .parse::<f64>()
        .map_err(|_| "invalid SGF komi")?;
    let mut game = Game::with_rules(size, komi, Rules::TrompTaylor).map_err(|e| e.to_string())?;
    let mut limited = (move_limit == Some(0)).then(|| game.clone());
    for (index, node) in nodes.iter().enumerate() {
        if ["AB", "AW", "AE", "HA"]
            .iter()
            .any(|key| node.contains_key(*key))
        {
            return Err("setup/handicap SGF import is unsupported".into());
        }
        if index > 0
            && ["FF", "GM", "CA", "SZ", "KM", "RU", "PL"]
                .iter()
                .any(|key| node.contains_key(*key))
        {
            return Err("midgame root/setup/rule properties are unsupported".into());
        }
        if node.contains_key("B") && node.contains_key("W") {
            return Err("two moves in one SGF node".into());
        }
        for (key, color) in [("B", Color::Black), ("W", Color::White)] {
            if node.contains_key(key) {
                if game.phase() != Phase::Playing {
                    return Err("moves after two-pass termination are unsupported".into());
                }
                let action = Move::from_sgf(single(node, key, "")?, size)
                    .map_err(|e| format!("invalid {key} move in node {}: {e}", index + 1))?;
                game.play_as(color, action)
                    .map_err(|e| format!("illegal move in node {}: {e}", index + 1))?;
                if move_limit == Some(game.history().len()) {
                    limited = Some(game.clone());
                }
            }
        }
    }
    Ok(limited.unwrap_or(game))
}

fn single<'a>(node: &'a Node, key: &str, default: &'a str) -> Result<&'a str, String> {
    match node.get(key) {
        None => Ok(default),
        Some(values) if values.len() == 1 => Ok(&values[0]),
        _ => Err(format!("multiple values for SGF property {key}")),
    }
}

struct Parser<'a> {
    input: &'a str,
    offset: usize,
}

impl Parser<'_> {
    fn peek(&self) -> Option<char> {
        self.input[self.offset..].chars().next()
    }

    fn bump(&mut self) -> Option<char> {
        let ch = self.peek()?;
        self.offset += ch.len_utf8();
        Some(ch)
    }

    fn space(&mut self) {
        while self.peek().is_some_and(char::is_whitespace) {
            self.bump();
        }
    }

    fn take(&mut self, expected: char) -> Result<(), String> {
        self.space();
        if self.peek() != Some(expected) {
            return Err(format!("expected '{expected}' at SGF byte {}", self.offset));
        }
        self.bump();
        Ok(())
    }

    fn value(&mut self) -> Result<String, String> {
        self.take('[')?;
        let mut out = String::new();
        while let Some(ch) = self.bump() {
            match ch {
                ']' => return Ok(out),
                '\\' => {
                    let escaped = self.bump().ok_or("unfinished SGF escape")?;
                    if matches!(escaped, '\r' | '\n') {
                        if self
                            .peek()
                            .is_some_and(|next| matches!(next, '\r' | '\n') && next != escaped)
                        {
                            self.bump();
                        }
                    } else {
                        out.push(escaped);
                    }
                }
                _ => out.push(ch),
            }
        }
        Err("unterminated SGF property value".into())
    }

    fn node(&mut self) -> Result<Node, String> {
        self.take(';')?;
        let mut node = Node::new();
        self.space();
        while self.peek().is_some_and(|ch| ch.is_ascii_uppercase()) {
            let start = self.offset;
            while self.peek().is_some_and(|ch| ch.is_ascii_uppercase()) {
                self.bump();
            }
            let key = self.input[start..self.offset].to_owned();
            if node.contains_key(&key) {
                return Err(format!("duplicate SGF property {key}"));
            }
            self.space();
            let mut values = Vec::new();
            while self.peek() == Some('[') {
                values.push(self.value()?);
                self.space();
            }
            if values.is_empty() {
                return Err(format!("SGF property {key} has no value"));
            }
            node.insert(key, values);
        }
        Ok(node)
    }

    fn tree(&mut self, depth: usize, selected: bool, nodes: &mut Vec<Node>) -> Result<(), String> {
        if depth > 128 {
            return Err("SGF nesting limit exceeded".into());
        }
        self.take('(')?;
        self.space();
        if self.peek() != Some(';') {
            return Err("empty SGF sequence".into());
        }
        while self.peek() == Some(';') {
            let node = self.node()?;
            if selected {
                nodes.push(node);
            }
        }
        let mut first_child = true;
        while self.peek() == Some('(') {
            self.tree(depth + 1, selected && first_child, nodes)?;
            first_child = false;
            self.space();
        }
        self.take(')')?;
        Ok(())
    }
}
