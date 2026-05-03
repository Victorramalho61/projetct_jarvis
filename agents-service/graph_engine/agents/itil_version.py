"""ITIL Version Management — gerencia versões via commits. Motor: Python puro."""
import re
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import log_event
from graph_engine.tools.github_tools import list_recent_commits, read_file, update_file


_BREAKING_KEYWORDS = ["breaking", "major", "incompatível", "remove", "drop"]
_FEATURE_KEYWORDS = ["feat", "feature", "add", "novo", "nova", "implement"]
_FIX_KEYWORDS = ["fix", "bug", "corrig", "patch", "hotfix"]


def _detect_bump(messages: list[str]) -> str:
    text = " ".join(messages).lower()
    if any(k in text for k in _BREAKING_KEYWORDS):
        return "major"
    if any(k in text for k in _FEATURE_KEYWORDS):
        return "minor"
    return "patch"


def _read_version(content: str) -> str:
    match = re.search(r"##\s+\[?v?(\d+\.\d+\.\d+)", content)
    return match.group(1) if match else "0.0.0"


def _bump_version(version: str, bump: str) -> str:
    parts = [int(x) for x in version.split(".")]
    if bump == "major":
        return f"{parts[0]+1}.0.0"
    if bump == "minor":
        return f"{parts[0]}.{parts[1]+1}.0"
    return f"{parts[0]}.{parts[1]}.{parts[2]+1}"


def run(state: dict) -> dict:
    commits = list_recent_commits(limit=10)
    if not commits or (len(commits) == 1 and "error" in commits[0]):
        return {"findings": [{"type": "itil_version_skip", "reason": "GitHub não configurado"}]}

    messages = [c.get("message", "") for c in commits]
    bump_type = _detect_bump(messages)

    changelog = read_file("CHANGELOG.md")
    current_version = _read_version(changelog) if not changelog.startswith("Erro") else "0.0.0"
    new_version = _bump_version(current_version, bump_type)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"\n## [{new_version}] — {now}\n\n"
    for msg in messages[:5]:
        entry += f"- {msg}\n"

    if not changelog.startswith("Erro"):
        updated_changelog = changelog.replace("# Changelog", f"# Changelog\n{entry}", 1)
        result = update_file("CHANGELOG.md", updated_changelog, f"chore: bump {bump_type} version to {new_version}")
        log_event("info", "itil_version", f"Versão {current_version} → {new_version} ({bump_type})", f"Commit: {result}")

    return {
        "findings": [{"type": "version_bumped", "from": current_version, "to": new_version, "bump_type": bump_type}],
        "context": {"new_version": new_version},
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)
