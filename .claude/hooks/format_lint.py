#!/usr/bin/env python3
"""Hook Claude Code (PostToolUse) : auto-format + lint des fichiers Python édités, via ruff.
Non bloquant : ne fait jamais échouer l'appel d'outil ; il range le fichier et signale.
Prérequis : `pip install ruff` (sinon le hook est ignoré silencieusement)."""
import json, shutil, subprocess, sys


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    path = (data.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py"):
        return 0
    if shutil.which("ruff") is None:
        print("hook: ruff non installé (pip install ruff) — formatage ignoré", file=sys.stderr)
        return 0
    subprocess.run(["ruff", "format", path], capture_output=True)
    subprocess.run(["ruff", "check", "--fix", path], capture_output=True)
    print(f"hook: ruff format + check --fix sur {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
