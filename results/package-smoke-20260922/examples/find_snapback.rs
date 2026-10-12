use goproverbs::engine::{Weights, rank_moves};
use goproverbs::search::{Limits, analyze};
use goproverbs::{BoardSize, Game, Move, Rules};
fn main() {
    let mut seed = 17u64;
    for _ in 0..300 {
        let mut g = Game::with_rules(BoardSize::new(5).unwrap(), 0.5, Rules::TrompTaylor).unwrap();
        for _ in 0..40 {
            let ranked = rank_moves(&g, g.to_play(), &Weights::default());
            let Some(first) = ranked.first() else {
                break;
            };
            if let Move::Play(p) = first.action {
                let mut after = g.clone();
                let captured = after.play(first.action).unwrap();
                if let Some(group) = after.board().group_at(p).unwrap()
                    && captured > 0
                    && group.liberties.len() == 1
                    && group.stones.len() > captured
                    && after.play(Move::Play(group.liberties[0])).is_ok()
                {
                    let a = analyze(
                        &g,
                        g.to_play(),
                        &Weights::default(),
                        Limits {
                            time_ms: 10000,
                            max_nodes: 100000,
                            max_depth: 2,
                            beam: 12,
                            tactical_plies: 0,
                            ..Limits::default()
                        },
                    )
                    .unwrap();
                    if a.action != first.action {
                        println!("{}", g.to_sgf());
                        println!(
                            "trap={} reply={} better={:?}",
                            p.to_gtp(g.board().size()).unwrap(),
                            group.liberties[0].to_gtp(g.board().size()).unwrap(),
                            a.action
                        );
                        for record in g.history() {
                            let s = match record.action {
                                Move::Pass => "pass".into(),
                                Move::Play(p) => p.to_gtp(g.board().size()).unwrap(),
                            };
                            println!("play {} {s}", record.color);
                        }
                        return;
                    }
                }
            }
            let legal: Vec<_> = ranked.iter().filter(|c| c.action != Move::Pass).collect();
            if legal.is_empty() {
                break;
            }
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
            g.play(legal[(seed as usize) % legal.len()].action).unwrap();
        }
    }
    panic!("no snapback fixture found");
}
