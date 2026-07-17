#!/usr/bin/env python3
"""trigger_eval.py — measure whether a skill's `description` actually triggers.

ARIS's known pain: with 80+ skills installed, Codex sometimes fails to
invoke the right skill for a query it should handle — and until now the only
lever (the frontmatter `description`) was tuned by pure judgment, with zero
measurement. This tool turns trigger behavior into a number.

MEASURE-ONLY BY DESIGN. It never rewrites a description. Its report is
EVIDENCE for a /meta-optimize proposal (which lands only via the human-gated
/meta-apply) — "a loop can drive, never acquit" applies to description tuning
too.

How it works (adapted from Anthropic's Claude Science `skill-creator`
run_eval.py — Apache-2.0; ported off its host.* runtime onto native Codex CLI):
- For each (skill, query), run `codex exec --json --ephemeral --sandbox
  read-only --skip-git-repo-check` as a subprocess FROM A NEUTRAL TEMP CWD.
  The user-level Codex skill
  corpus is loaded as usual, so the measurement happens under the REALISTIC
  long installed list — the exact condition under which omission happens (an
  isolated one-skill sandbox would trivially inflate trigger rates).
- Parse the JSONL stream for `command_execution` items that read a SKILL.md.
  Reading the target first counts as a TRIGGER; reading a different skill first
  is a CONFUSION (recorded by name); no skill read is a MISS.
- SAFETY: `--sandbox read-only` prevents probed work from changing the
  filesystem and blocks network access, while `--ephemeral` avoids persisting
  the session. The probe runs in an empty temporary directory and permits only
  the read-only commands needed for Codex to discover and load a skill.

Query-set methodology (see trigger_evals.sample.json): queries must PARAPHRASE
user intent, never quote the description's own trigger phrases verbatim — a
query containing the literal trigger string is trivially positive and measures
nothing. Optional negative queries (expect: none) measure false-triggering.

Usage:
  python3 tools/meta_opt/trigger_eval.py --eval-file tools/meta_opt/trigger_evals.sample.json \\
      [--skills check-gpu,research-lit] [--samples 2] [--model haiku] \\
      [--out .aris/meta/trigger_report.json] [--timeout 120]

Exit code: 0 on completed run (regardless of rates), 2 on setup error.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------- pure logic


def parse_stream_tool_uses(stream_text: str):
    """Extract Codex command executions from a `codex exec --json` stream."""
    uses = []
    for line in stream_text.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") not in {"item.started", "item.completed"}:
            continue
        item = ev.get("item") or {}
        if item.get("type") != "command_execution":
            continue
        pair = ("command_execution", {"command": item.get("command") or ""})
        # Codex emits started and completed events for the same execution.
        if pair not in uses:
            uses.append(pair)
    return uses


def classify(tool_uses, target_skill: str):
    """Classify one probe run: ('trigger'|'confusion'|'miss', detail).

    Trigger: the first SKILL.md read is for the target.
    Confusion: the first SKILL.md read is for another skill (detail = its name).
    Miss: no skill engagement at all.
    """
    for name, inp in tool_uses:
        if name != "command_execution":
            continue
        command = str(inp.get("command") or "")
        if "/SKILL.md" not in command:
            continue
        prefix = command.split("/SKILL.md", 1)[0].rstrip("'\"")
        invoked = prefix.rsplit("/", 1)[-1]
        target_basename = target_skill.rsplit(":", 1)[-1]
        if invoked == target_basename:
            detail = (
                invoked if invoked == target_skill else f"{invoked} ({target_skill})"
            )
            return "trigger", detail
        return "confusion", invoked
    return "miss", ""


def aggregate(records):
    """records: list of {skill, query, outcome, detail} → per-skill summary."""
    out = {}
    for r in records:
        s = out.setdefault(
            r["skill"],
            {
                "probes": 0,
                "triggers": 0,
                "misses": 0,
                "errors": 0,
                "confusions": {},
                "queries": {},
            },
        )
        s["probes"] += 1
        q = s["queries"].setdefault(
            r["query"], {"trigger": 0, "confusion": 0, "miss": 0, "error": 0}
        )
        q[r["outcome"]] += 1
        if r["outcome"] == "trigger":
            s["triggers"] += 1
        elif r["outcome"] == "miss":
            s["misses"] += 1
        elif r["outcome"] == "error":
            s["errors"] += 1
        elif r["outcome"] == "confusion":
            s["confusions"][r["detail"]] = s["confusions"].get(r["detail"], 0) + 1
    for s in out.values():
        graded = s["probes"] - s["errors"]
        s["trigger_rate"] = round(s["triggers"] / graded, 3) if graded else None
    return out


# ------------------------------------------------------------------- probing


def _stream_real_error(stream_text: str) -> bool:
    """True iff Codex emitted a failed turn."""
    for line in stream_text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "turn.failed":
            return True
    return False


def _stream_has_assistant(stream_text: str) -> bool:
    """True iff Codex produced an agent message or completed the turn."""
    for line in stream_text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
            if ev.get("type") == "turn.completed":
                return True
            if (
                ev.get("type") == "item.completed"
                and (ev.get("item") or {}).get("type") == "agent_message"
            ):
                return True
        except json.JSONDecodeError:
            continue
    return False


def run_probe(query: str, model: str | None, timeout: int, cwd: str) -> str:
    """Run one native Codex probe and return its JSONL event stream."""
    cmd = [
        "codex",
        "exec",
        "--json",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
    ]
    if model:
        cmd += ["--model", model]
    result = subprocess.run(
        cmd, input=query, capture_output=True, text=True, timeout=timeout, cwd=cwd
    )
    if _stream_real_error(result.stdout):
        raise RuntimeError("codex exec stream carried a turn.failed event")
    if _stream_has_assistant(result.stdout):
        return result.stdout
    if result.returncode != 0:
        raise RuntimeError(
            f"codex exec exited {result.returncode} with no assistant "
            f"turn: {result.stderr.strip()[:300]}"
        )
    return result.stdout  # clean, no tool call → graded miss


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Measure skill-description trigger rates.")
    ap.add_argument(
        "--eval-file", required=True, help='JSON: {"<skill>": ["query", ...], ...}'
    )
    ap.add_argument(
        "--skills",
        default="",
        help="comma-separated subset of skills to probe (default: all in file)",
    )
    ap.add_argument(
        "--samples",
        type=int,
        default=3,
        help="probes per query (trigger behavior is stochastic; the "
        "default 3 matches the upstream eval — samples=1 is too "
        "noisy to act on)",
    )
    ap.add_argument(
        "--model",
        default=None,
        help="model override for probes (default: Codex CLI default). "
        "NB: trigger behavior is model-dependent — compare like with like.",
    )
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--out", default=".aris/meta/trigger_report.json")
    args = ap.parse_args(argv)

    try:
        evals = json.loads(Path(args.eval_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read eval file: {e}", file=sys.stderr)
        return 2
    subset = {s.strip() for s in args.skills.split(",") if s.strip()}
    targets = {
        k: v
        for k, v in evals.items()
        if (not subset or k in subset) and not k.startswith("_")
    }
    if not targets:
        print("ERROR: no skills selected", file=sys.stderr)
        return 2

    records = []
    # Neutral cwd: no project-level .agents/, so probes see exactly the
    # user-level installed corpus — the realistic long list.
    with tempfile.TemporaryDirectory(prefix="trigger-eval-") as neutral_cwd:
        for skill, queries in targets.items():
            for query in queries:
                for _ in range(args.samples):
                    try:
                        stream = run_probe(query, args.model, args.timeout, neutral_cwd)
                        outcome, detail = classify(
                            parse_stream_tool_uses(stream), skill
                        )
                    except (RuntimeError, subprocess.TimeoutExpired) as e:
                        outcome, detail = "error", str(e)[:200]
                    records.append(
                        {
                            "skill": skill,
                            "query": query,
                            "outcome": outcome,
                            "detail": detail,
                        }
                    )
                    print(
                        f"  [{outcome:9}] {skill} ← {query[:60]!r}"
                        + (f" → {detail}" if outcome == "confusion" else "")
                    )

    summary = aggregate(records)
    report = {
        "model": args.model or "cli-default",
        "samples": args.samples,
        "skills": summary,
        "records": records,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nskill                          rate   probes  confusions")
    for name, s in sorted(summary.items()):
        conf = (
            ", ".join(
                f"{k}×{v}"
                for k, v in sorted(s["confusions"].items(), key=lambda kv: -kv[1])
            )
            or "-"
        )
        rate = "n/a " if s["trigger_rate"] is None else f"{s['trigger_rate']:.2f}"
        print(f"{name:30} {rate}   {s['probes']:4}    {conf}")
    print(f"\nreport → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
