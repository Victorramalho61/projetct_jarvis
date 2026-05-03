"""Ferramentas GitHub para agentes de docs e code review."""
import base64
import logging

from db import get_settings

log = logging.getLogger(__name__)


def _get_repo():
    s = get_settings()
    if not s.github_token or not s.github_repo:
        return None, None
    try:
        from github import Github
        g = Github(s.github_token)
        return g, g.get_repo(s.github_repo)
    except Exception as e:
        log.warning("GitHub client error: %s", e)
        return None, None


def list_recent_commits(branch: str = "main", limit: int = 10) -> list[dict]:
    _, repo = _get_repo()
    if not repo:
        return []
    try:
        commits = list(repo.get_commits(sha=branch))[:limit]
        result = []
        for c in commits:
            files = []
            try:
                for f in c.files:
                    files.append({
                        "filename": f.filename,
                        "status": f.status,
                        "additions": f.additions,
                        "deletions": f.deletions,
                        "patch": f.patch or "",
                    })
            except Exception:
                pass
            result.append({
                "sha": c.sha,
                "message": c.commit.message.split("\n")[0],
                "author": c.commit.author.name,
                "date": c.commit.author.date.isoformat(),
                "files": files,
            })
        return result
    except Exception as e:
        log.warning("list_recent_commits error: %s", e)
        return []


def list_workflow_runs(since_minutes: int = 30) -> list[dict]:
    """Lista GitHub Actions workflow runs recentes."""
    _, repo = _get_repo()
    if not repo:
        return []
    try:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        runs = []
        for wf in repo.get_workflows():
            for run in wf.get_runs()[:5]:
                if run.created_at.replace(tzinfo=timezone.utc) < cutoff:
                    break
                runs.append({
                    "id": run.id,
                    "name": wf.name,
                    "event": run.event,
                    "status": run.status,
                    "conclusion": run.conclusion,
                    "head_branch": run.head_branch,
                    "html_url": run.html_url,
                    "created_at": run.created_at.isoformat(),
                })
        return runs
    except Exception as e:
        log.warning("list_workflow_runs error: %s", e)
        return []


def get_file_diff(filename: str, sha: str) -> str:
    """Retorna o patch/diff de um arquivo em um commit espec�fico."""
    _, repo = _get_repo()
    if not repo:
        return ""
    try:
        commit = repo.get_commit(sha)
        for f in commit.files:
            if f.filename == filename:
                return f.patch or ""
        return ""
    except Exception as e:
        log.warning("get_file_diff(%s, %s) error: %s", filename, sha, e)
        return ""


def get_pr_status(pr_number: int | None = None) -> list[dict]:
    """Retorna PRs abertos ou um PR espec�fico."""
    _, repo = _get_repo()
    if not repo:
        return []
    try:
        if pr_number:
            pr = repo.get_pull(pr_number)
            return [{"number": pr.number, "title": pr.title, "state": pr.state, "merged": pr.merged, "base": pr.base.ref, "head": pr.head.ref}]
        prs = repo.get_pulls(state="open")[:10]
        return [{"number": p.number, "title": p.title, "state": p.state, "base": p.base.ref, "head": p.head.ref, "created_at": p.created_at.isoformat()} for p in prs]
    except Exception as e:
        log.warning("get_pr_status error: %s", e)
        return []


def read_file(path: str) -> str:
    _, repo = _get_repo()
    if not repo:
        return "GitHub n�o configurado"
    try:
        content = repo.get_contents(path)
        return base64.b64decode(content.content).decode("utf-8")
    except Exception as e:
        return f"Erro ao ler {path}: {e}"


def update_file(path: str, content: str, commit_message: str, branch: str = "main") -> dict:
    _, repo = _get_repo()
    if not repo:
        return {"success": False, "error": "GitHub n�o configurado"}
    try:
        try:
            existing = repo.get_contents(path, ref=branch)
            repo.update_file(path, commit_message, content, existing.sha, branch=branch)
        except Exception:
            repo.create_file(path, commit_message, content, branch=branch)
        return {"success": True, "path": path}
    except Exception as e:
        log.warning("update_file(%s) error: %s", path, e)
        return {"success": False, "error": str(e)}


def create_issue(title: str, body: str, labels: list[str] | None = None) -> dict:
    _, repo = _get_repo()
    if not repo:
        return {"success": False, "error": "GitHub n�o configurado"}
    try:
        issue = repo.create_issue(title=title, body=body, labels=labels or [])
        return {"success": True, "number": issue.number, "url": issue.html_url}
    except Exception as e:
        return {"success": False, "error": str(e)}
