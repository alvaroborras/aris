#!/usr/bin/env python3
"""Install/remove ARIS-owned entries in a project-local Codex hooks.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

VERSION = 1
OWNERSHIP = ".aris/installed-codex-hooks.json"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def entries(repo: Path, project: Path) -> list[tuple[str, dict[str, Any]]]:
    command = 'python3 "$(git rev-parse --show-toplevel)/.codex/hooks/aris_hook.sh"'
    return [
        (
            "SessionStart",
            {
                "matcher": "startup|resume|clear|compact",
                "hooks": [{"type": "command", "command": command + " --mode logger"}],
            },
        ),
        (
            "UserPromptSubmit",
            {"hooks": [{"type": "command", "command": command + " --mode logger"}]},
        ),
        (
            "PostToolUse",
            {"hooks": [{"type": "command", "command": command + " --mode logger"}]},
        ),
        (
            "Stop",
            {"hooks": [{"type": "command", "command": command + " --mode readiness"}]},
        ),
        (
            "PreToolUse",
            {
                "matcher": "^Bash$",
                "hooks": [{"type": "command", "command": command + " --mode guard"}],
            },
        ),
    ]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"hooks": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed Codex hook configuration: {path} ({exc})") from exc
    if not isinstance(value, dict) or (
        "hooks" in value and not isinstance(value["hooks"], dict)
    ):
        raise ValueError(f"invalid Codex hook configuration shape: {path}")
    value.setdefault("hooks", {})
    return value


def load_ownership(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": VERSION, "entries": []}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"malformed ARIS hook ownership manifest: {path} ({exc})"
        ) from exc
    if (
        not isinstance(value, dict)
        or value.get("version") != VERSION
        or not isinstance(value.get("entries"), list)
    ):
        raise ValueError(f"invalid ARIS hook ownership manifest: {path}")
    return value


def same_entry(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return canonical(left) == canonical(right)


def install(project: Path, repo: Path, *, dry_run: bool, opt_out: bool) -> None:
    codex = project / ".codex"
    config_path = codex / "hooks.json"
    ownership_path = project / OWNERSHIP
    if opt_out:
        return
    config = load_json(config_path)
    ownership = load_ownership(ownership_path)
    hooks = config["hooks"]
    desired = entries(repo, project)
    old_owned = {
        (x["event"], x["matcher"], x["command"]): x for x in ownership["entries"]
    }
    new_owned: list[dict[str, str]] = []
    for event, group in desired:
        matcher = group.get("matcher", "")
        command = group["hooks"][0]["command"]
        existing = hooks.setdefault(event, [])
        if not isinstance(existing, list):
            raise ValueError(f"invalid Codex hook event shape for {event}")
        matches = [
            i
            for i, candidate in enumerate(existing)
            if isinstance(candidate, dict) and same_entry(candidate, group)
        ]
        if not matches:
            # A changed ARIS-owned command is a conflict, not an opportunity to
            # delete a possibly user-edited hook.
            for owned in old_owned.values():
                if owned["event"] == event and owned["matcher"] == matcher:
                    raise ValueError(
                        f"conflicting ARIS-owned hook entry for {event} ({matcher or '*'})"
                    )
            existing.append(group)
        new_owned.append(
            {
                "event": event,
                "matcher": matcher,
                "command": command,
                "sha256": digest(group),
            }
        )
    if dry_run:
        return
    codex.mkdir(parents=True, exist_ok=True)
    launcher = codex / "hooks/aris_hook.sh"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\n\nROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"\nMANIFEST="$ROOT/.aris/installed-skills-codex.txt"\nARIS_REPO=""\nif [[ -f "$MANIFEST" ]]; then\n  ARIS_REPO="$(awk -F\'\\t\' \'$1=="repo_root"{print $2; exit}\' "$MANIFEST")"\nfi\nif [[ -z "$ARIS_REPO" || ! -f "$ARIS_REPO/tools/meta_opt/hook_adapter.py" ]]; then\n  echo \'ARIS Codex hook launcher: repo_root unresolved from .aris/installed-skills-codex.txt\' >&2\n  exit 0\nfi\nexec python3 "$ARIS_REPO/tools/meta_opt/hook_adapter.py" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    ownership_path.parent.mkdir(parents=True, exist_ok=True)
    ownership_path.write_text(
        json.dumps(
            {"version": VERSION, "repo_root": str(repo), "entries": new_owned}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )


def uninstall(project: Path, *, dry_run: bool) -> None:
    config_path = project / ".codex/hooks.json"
    ownership_path = project / OWNERSHIP
    if not ownership_path.exists():
        return
    config = load_json(config_path)
    ownership = load_ownership(ownership_path)
    for owned in ownership["entries"]:
        event = owned["event"]
        groups = config["hooks"].get(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"invalid Codex hook event shape for {event}")
        kept = []
        for group in groups:
            if not isinstance(group, dict):
                kept.append(group)
                continue
            commands = group.get("hooks", [])
            command = (
                commands[0].get("command")
                if isinstance(commands, list)
                and commands
                and isinstance(commands[0], dict)
                else None
            )
            matcher = group.get("matcher", "")
            if (
                event == owned["event"]
                and matcher == owned["matcher"]
                and command == owned["command"]
                and digest(group) == owned["sha256"]
            ):
                continue
            kept.append(group)
        if kept:
            config["hooks"][event] = kept
        else:
            config["hooks"].pop(event, None)
    if dry_run:
        return
    if config["hooks"]:
        config_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    elif config_path.exists():
        config_path.unlink()
    launcher = project / ".codex/hooks/aris_hook.sh"
    if launcher.exists():
        launcher.unlink()
    if launcher.parent.exists() and not any(launcher.parent.iterdir()):
        launcher.parent.rmdir()
    ownership_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--action", choices=("install", "uninstall"), default="install")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-meta-hooks", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "uninstall":
            uninstall(args.project.resolve(), dry_run=args.dry_run)
        else:
            install(
                args.project.resolve(),
                args.repo.resolve(),
                dry_run=args.dry_run,
                opt_out=args.no_meta_hooks,
            )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
