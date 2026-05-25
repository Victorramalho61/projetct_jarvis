import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException

from auth import require_role

router = APIRouter(prefix="/api/hermes")

SKILLS_DIR = Path("/root/.hermes/skills")
CONVERSATIONS_DIR = Path("/root/.hermes/conversations")


def _parse_skill_file(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(text) or {}
        elif path.suffix == ".json":
            data = json.loads(text)
        else:
            # plain text skill
            data = {"name": path.stem, "description": text[:200].strip()}
        return {
            "name": data.get("name", path.stem),
            "description": data.get("description", ""),
            "tags": data.get("tags", []),
            "uses": data.get("uses", 0),
            "modified_at": path.stat().st_mtime,
            "file": path.name,
        }
    except Exception:
        return None


@router.get("/skills")
def list_skills(_: dict = Depends(require_role("admin"))):
    if not SKILLS_DIR.exists():
        return []
    skills = []
    for path in sorted(SKILLS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.is_file():
            skill = _parse_skill_file(path)
            if skill:
                skills.append(skill)
    return skills


@router.delete("/skills/{filename}")
def delete_skill(filename: str, _: dict = Depends(require_role("admin"))):
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(400, detail="Nome de arquivo inválido")
    path = SKILLS_DIR / filename
    if not path.exists():
        raise HTTPException(404, detail="Skill não encontrada")
    path.unlink()
    return {"status": "deleted"}


@router.get("/conversations")
def list_conversations(_: dict = Depends(require_role("admin"))):
    if not CONVERSATIONS_DIR.exists():
        return []
    convs = []
    for path in sorted(
        CONVERSATIONS_DIR.iterdir(),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:50]:
        if path.is_file():
            convs.append({
                "file": path.name,
                "size_bytes": path.stat().st_size,
                "modified_at": path.stat().st_mtime,
            })
    return convs
