"""CPU-only GTP evaluation/tuning with an independent Tromp-Taylor referee.

No third-party Python packages. Fixture tuning learns move-order weights only;
search evaluation weights remain unchanged. It is not a strength optimizer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import random
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"


class GTP:
    def __init__(self, exe, profile=None, size=9, nodes=500, depth=3, beam=6, tactical=0, search_mode="selective", shortlist=3, time_ms=1000):
        cmd = [str(exe), "--gtp", "--rules", "tt", "--size", str(size),
               "--time-ms", str(time_ms), "--nodes", str(nodes), "--depth", str(depth), "--beam", str(beam)]
        if profile:
            cmd += ["--profile", str(profile)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.lines = queue.Queue()
        self.errors = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=lambda: self.errors.extend(self.proc.stderr), daemon=True).start()
        self.number = 0
        try:
            if search_mode != "selective":
                self.command(f"gp-mode {search_mode}")
            if shortlist != 3:
                self.command(f"gp-shortlist {shortlist}")
            if tactical:
                self.command(f"gp-tactical {tactical}")
        except BaseException:
            self.close()
            raise

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(line.rstrip("\r\n"))
        self.lines.put(None)

    def command(self, text):
        self.number += 1
        self.proc.stdin.write(f"{self.number} {text}\n")
        self.proc.stdin.flush()
        lines = []
        deadline = time.monotonic() + 15
        while True:
            line = self.lines.get(timeout=max(0.01, deadline - time.monotonic()))
            if line is None:
                raise RuntimeError("engine exited: " + "".join(self.errors))
            if line == "":
                break
            lines.append(line)
        if not lines or not lines[0].startswith(f"={self.number}"):
            raise RuntimeError(f"{text}: {lines}")
        return "\n".join([lines[0][len(str(self.number)) + 1:].lstrip()] + lines[1:]).strip()

    def close(self):
        try:
            if self.proc.poll() is None:
                self.command("quit")
                self.proc.wait(timeout=3)
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait()
            for pipe in [self.proc.stdin, self.proc.stdout, self.proc.stderr]:
                pipe.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Referee:
    """Independent board, capture, suicide, positional-superko and area scoring."""
    def __init__(self, size, komi=0.5):
        self.size, self.komi = size, komi
        self.board = ["."] * (size * size)
        self.seen = {tuple(self.board)}
        self.passes = 0

    def neighbors(self, p):
        x, y = p % self.size, p // self.size
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            xx, yy = x + dx, y + dy
            if 0 <= xx < self.size and 0 <= yy < self.size:
                yield yy * self.size + xx

    def group(self, board, p):
        color = board[p]
        chain, liberties, stack = {p}, set(), [p]
        while stack:
            for n in self.neighbors(stack.pop()):
                if board[n] == color:
                    if n not in chain:
                        chain.add(n)
                        stack.append(n)
                elif board[n] == ".":
                    liberties.add(n)
        return chain, liberties

    def play(self, color, vertex):
        if vertex == "pass":
            self.passes += 1
            return
        x, y = COLUMNS.index(vertex[0].upper()), self.size - int(vertex[1:])
        assert 0 <= x < self.size and 0 <= y < self.size
        point = y * self.size + x
        assert self.board[point] == ".", "occupied"
        board = self.board.copy()
        board[point] = color
        other = "W" if color == "B" else "B"
        for n in self.neighbors(point):
            if board[n] == other:
                group, liberties = self.group(board, n)
                if not liberties:
                    for p in group:
                        board[p] = "."
        group, liberties = self.group(board, point)
        if not liberties:
            for p in group:
                board[p] = "."
        state = tuple(board)
        assert state not in self.seen, "positional superko"
        self.board = board
        self.seen.add(state)
        self.passes = 0

    def margin(self):
        totals = {"B": self.board.count("B"), "W": self.board.count("W")}
        seen = set()
        for p, cell in enumerate(self.board):
            if cell != "." or p in seen:
                continue
            region, _ = self.group(self.board, p)
            seen.update(region)
            borders = {self.board[n] for q in region for n in self.neighbors(q)} - {"."}
            if len(borders) == 1:
                totals[next(iter(borders))] += len(region)
        return totals["B"] - totals["W"] - self.komi

    def compare(self, diagram):
        cells = []
        for line in diagram.splitlines():
            parts = line.split()
            if parts and parts[0].isdigit():
                cells.extend({"X": "B", "O": "W", "+": ".", ".": "."}[c] for c in parts[1:-1])
        assert cells == self.board, "engine and independent referee disagree"


def load_cases(path):
    cases = json.loads(Path(path).read_text())
    identities = set()
    family_split = {}
    for case in cases:
        assert case["id"] not in identities
        identities.add(case["id"])
        family = case["family"]
        assert family not in family_split or family_split[family] == case["split"], "family leakage"
        family_split[family] = case["split"]
    return cases


def setup(engine, case):
    engine.command(f"boardsize {case['size']}")
    engine.command("komi 0.5")
    ref = Referee(case["size"])
    for color, move in case["moves"]:
        engine.command(f"play {color} {move}")
        ref.play(color, move)
    ref.compare(engine.command("showboard"))
    return ref


def acceptable(case, move):
    if "accept" in case:
        return move in case["accept"]
    return move not in case.get("reject", []) and (move != "pass" or case.get("allow_pass", False))


def candidates(engine, color):
    result = []
    for line in engine.command(f"gp-candidates {color}").splitlines():
        fields = line.split()
        features = {name: float(value) for name, value in (x.split(":") for x in fields[2:])}
        result.append((fields[0], float(fields[1]), features))
    return result


def read_weights(path):
    return {k.strip(): float(v) for k, v in (line.split("#")[0].split("=", 1)
            for line in Path(path).read_text().splitlines() if "=" in line.split("#")[0])}


def tune(args):
    cases = load_cases(args.fixtures)
    train = [c for c in cases if c["split"] == "train"]
    original = read_weights(args.profile)
    data = []
    with GTP(args.exe, args.profile) as engine:
        for case in train:
            setup(engine, case)
            rows = candidates(engine, case["color"])
            assert any(acceptable(case, r[0]) for r in rows), case["id"]
            data.append((case, rows))

    def objective(weights):
        total = 0.0
        for case, rows in data:
            scored = [(0.01 * (move != "pass") + sum(weights[k] * v for k, v in features.items()), move)
                      for move, _, features in rows]
            good = max(score for score, move in scored if acceptable(case, move))
            bad = max((score for score, move in scored if not acceptable(case, move)), default=good - 3)
            selected = max(range(len(scored)), key=lambda i: scored[i][0])
            total += int(acceptable(case, scored[selected][1])) + 0.1 * max(-3, min(3, good - bad))
        penalty = 0.0005 * sum((weights[k] - original[k]) ** 2 for k in weights)
        return total / len(data) - penalty

    ranges = {"capture": (0, 20), "save_atari": (0, 24), "self_atari": (-30, 0),
              "connect": (-4, 6), "fill_eye": (-30, 0), "empty_corner": (0, 8),
              "side_development": (-2, 4), "early_33": (-2, 4), "atari": (0, 12), "cut_pressure": (-4, 8)}
    weights = dict(original)
    before = objective(weights)
    steps = []
    for step in [2.0, 1.0, 0.5, 0.25]:
        for _ in range(3):
            changed = False
            for name, (low, high) in ranges.items():
                best = objective(weights)
                chosen = weights[name]
                for direction in [-1, 1]:
                    proposal = dict(weights)
                    proposal[name] = max(low, min(high, weights[name] + direction * step))
                    value = objective(proposal)
                    if value > best + 1e-12:
                        best, chosen = value, proposal[name]
                if chosen != weights[name]:
                    weights[name] = chosen
                    steps.append({"feature": name, "value": chosen, "objective": best})
                    changed = True
            if not changed:
                break
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    assert path.resolve() != Path(args.profile).resolve(), "do not overwrite the baseline"
    path.write_text("# Experimental fixture-tuned move-order weights; not a strength claim.\n" +
                    "".join(f"{k}={v:g}\n" for k, v in weights.items()), encoding="ascii")
    report = {"training_ids": [c["id"] for c in train], "held_out_used_for_optimization": False,
              "training_sha256": hashlib.sha256(json.dumps(train, sort_keys=True).encode()).hexdigest(),
              "executable_sha256": hashlib.sha256(args.exe.read_bytes()).hexdigest(),
              "input_profile_sha256": hashlib.sha256(args.profile.read_bytes()).hexdigest(),
              "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "objective_before": before, "objective_after": objective(weights), "steps": steps,
              "position_evaluation_weights_tuned": False, "weights": weights}
    path.with_suffix(".tuning.json").write_text(json.dumps(report, indent=2), encoding="ascii")
    print(json.dumps(report, indent=2), flush=True)


def evaluate_fixtures(args):
    rows = []
    with GTP(args.exe, args.profile, nodes=args.nodes, depth=args.depth, beam=args.beam, tactical=args.tactical, search_mode=args.search, shortlist=args.shortlist, time_ms=args.time_ms) as engine:
        for case in load_cases(args.fixtures):
            setup(engine, case)
            ranked = candidates(engine, case["color"])
            started = time.perf_counter()
            report = engine.command(f"gp-search {case['color']}")
            info = dict(field.split("=", 1) for field in report.splitlines()[0].split())
            row = {"id": case["id"], "split": case["split"], "baseline_move": ranked[0][0],
                   "baseline_pass": acceptable(case, ranked[0][0]), "search_move": info["move"],
                   "search_pass": acceptable(case, info["move"]), "depth": int(info["depth"]),
                   "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "report": report}
            rows.append(row)
            print(f"{case['id']}: baseline={row['baseline_pass']} search={row['search_pass']} depth={row['depth']}", flush=True)
    return {"fixtures": rows, "summary": {split: {
        "total": sum(r["split"] == split for r in rows),
        "baseline_pass": sum(r["split"] == split and r["baseline_pass"] for r in rows),
        "search_pass": sum(r["split"] == split and r["search_pass"] for r in rows)} for split in ["train", "test"]}}


def arena(args):
    records = []
    rng = random.Random(args.seed)
    openings = []
    for _ in range(args.pairs):
        ref = Referee(args.size)
        opening = []
        for color in ["B", "W"]:
            choices = [f"{COLUMNS[x]}{y + 1}" for x in range(args.size) for y in range(args.size)]
            rng.shuffle(choices)
            for move in choices:
                try:
                    ref.play(color, move)
                    opening.append((color, move))
                    break
                except AssertionError:
                    continue
        openings.append(opening)
    for pair, opening in enumerate(openings):
        for search_color in ["B", "W"]:
            ref = Referee(args.size)
            prefix = Path(args.output).parent / f"game-{pair}-{search_color}"
            with GTP(args.exe, args.profile, args.size, args.nodes, args.depth, args.beam, args.tactical, args.search, args.shortlist, args.time_ms) as engine:
                engine.command("komi 0.5")
                for color, move in opening:
                    engine.command(f"play {color} {move}")
                    ref.play(color, move)
                decisions = []
                finished = False
                for turn in range(args.size * args.size * 4):
                    color = "B" if turn % 2 == 0 else "W"
                    started = time.perf_counter()
                    if color == search_color:
                        move = engine.command(f"genmove {color}")
                        trace = engine.command("gp-last-search")
                    else:
                        move = candidates(engine, color)[0][0]
                        engine.command(f"play {color} {move}")
                        trace = "one-ply weighted baseline"
                    ref.play(color, move)
                    ref.compare(engine.command("showboard"))
                    decisions.append({"color": color, "move": move, "ms": round((time.perf_counter() - started) * 1000, 3), "trace": trace})
                    if ref.passes == 2:
                        finished = True
                        break
                margin = ref.margin()
                winner = "B" if margin > 0 else "W" if margin < 0 else "draw"
                result = engine.command("final_score") if finished else "unfinished"
                if finished:
                    expected = f"{winner}+{abs(margin):g}" if winner != "draw" else "0"
                    assert result == expected, (result, expected)
                prefix.with_suffix(".sgf").write_text(engine.command("gp-sgf"), encoding="ascii")
                prefix.with_suffix(".json").write_text(json.dumps(decisions, indent=2), encoding="ascii")
                records.append({"pair": pair, "opening": opening, "search_color": search_color,
                    "finished": finished, "result": result, "moves": len(decisions) + len(opening),
                    "search_won": finished and winner == search_color, "final_board_margin": margin})
                print(f"pair={pair} search={search_color} result={result} moves={records[-1]['moves']}", flush=True)
    return {"games": records, "completed": sum(r["finished"] for r in records),
            "search_wins": sum(r["search_won"] for r in records),
            "unfinished": sum(not r["finished"] for r in records),
            "independent_referee_checked_every_move_and_final_score": True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["tune", "evaluate", "arena"])
    p.add_argument("--exe", type=Path, default=ROOT / "target/release/goproverbs.exe")
    p.add_argument("--profile", type=Path, default=ROOT / "profiles/baseline.weights")
    p.add_argument("--fixtures", type=Path, default=ROOT / "benchmarks/fixtures.json")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--nodes", type=int, default=500)
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--beam", type=int, default=6)
    p.add_argument("--search", choices=["selective", "full", "minimax", "hybrid"], default="selective")
    p.add_argument("--shortlist", type=int, default=3)
    p.add_argument("--time-ms", type=int, default=1000)
    p.add_argument("--tactical", type=int, choices=range(5), default=0)
    p.add_argument("--size", type=int, default=5)
    p.add_argument("--pairs", type=int, default=2)
    p.add_argument("--seed", type=int, default=20260920)
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "tune":
        tune(args)
        return
    result = evaluate_fixtures(args) if args.mode == "evaluate" else arena(args)
    result.update({"executable_sha256": hashlib.sha256(args.exe.read_bytes()).hexdigest(),
                   "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "fixtures_sha256": hashlib.sha256(args.fixtures.read_bytes()).hexdigest(),
                   "profile_sha256": hashlib.sha256(args.profile.read_bytes()).hexdigest(),
                   "limits": {"nodes": args.nodes, "depth": args.depth, "beam": args.beam, "ms": args.time_ms, "tactical": args.tactical, "search": args.search, "shortlist": args.shortlist},
                   "seed": args.seed, "mode": args.mode})
    args.output.write_text(json.dumps(result, indent=2), encoding="ascii")
    print(json.dumps({k: v for k, v in result.items() if k not in ["games", "fixtures"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
