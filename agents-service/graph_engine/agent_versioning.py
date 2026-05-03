"""
Agent Versioning — ciclo de vida e rollback de versões de agentes.
Persiste em Supabase (tabela agent_versions).

Fluxo: draft → testing → approved ↔ canary → deprecated
Rollback: deprecated a versão nova, reativa a anterior.
"""
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# ── Estados ─────────────────────────────────────────────────────────────────

VALID_STATUSES = ("draft", "testing", "approved", "canary", "deprecated")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_prompt(system_prompt: str, tools: list) -> str:
    content = f"{system_prompt}:{json.dumps(sorted(tools))}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ── Registry (Supabase-backed) ───────────────────────────────────────────────

class AgentRegistry:
    """Gerencia versões de agentes via tabela agent_versions no Supabase."""

    def __init__(self):
        from db import get_supabase
        self._db = get_supabase()

    # ── Leitura ──────────────────────────────────────────────────────────────

    def list_versions(self, agent_name: str) -> list[dict]:
        return (
            self._db.table("agent_versions")
            .select("*")
            .eq("agent_name", agent_name)
            .order("created_at", desc=True)
            .execute()
            .data or []
        )

    def get_active(self, agent_name: str) -> Optional[dict]:
        """Retorna versão approved mais recente (prioridade) ou canary."""
        rows = (
            self._db.table("agent_versions")
            .select("*")
            .eq("agent_name", agent_name)
            .in_("status", ["approved", "canary"])
            .order("approved_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        return rows[0] if rows else None

    def get_version(self, agent_name: str, version: str) -> Optional[dict]:
        rows = (
            self._db.table("agent_versions")
            .select("*")
            .eq("agent_name", agent_name)
            .eq("version", version)
            .limit(1)
            .execute()
            .data
        )
        return rows[0] if rows else None

    # ── Escrita ──────────────────────────────────────────────────────────────

    def register(
        self,
        agent_name: str,
        version: str,
        system_prompt: str,
        tools: list,
        model: str = "llama3.2:1b",
        config: dict | None = None,
        created_by: str = "system",
        notes: str = "",
        parent_version: str | None = None,
    ) -> dict:
        """Registra nova versão em status draft."""
        existing = self.get_version(agent_name, version)
        if existing:
            raise ValueError(f"Versão {agent_name}:{version} já existe")

        parent_id = None
        if parent_version:
            pv = self.get_version(agent_name, parent_version)
            if pv:
                parent_id = pv["id"]

        row = {
            "agent_name": agent_name,
            "version": version,
            "status": "draft",
            "system_prompt": system_prompt,
            "tools": tools,
            "model": model,
            "config": config or {},
            "prompt_hash": _hash_prompt(system_prompt, tools),
            "created_by": created_by,
            "parent_version_id": parent_id,
            "notes": notes,
            "failure_count": 0,
            "total_runs": 0,
            "success_rate": 0.0,
            "canary_percentage": 0,
        }
        result = self._db.table("agent_versions").insert(row).execute()
        return result.data[0]

    def mark_testing(self, agent_name: str, version: str) -> dict:
        return self._update_status(agent_name, version, "testing")

    def mark_approved(self, agent_name: str, version: str, approved_by: str = "system") -> dict:
        """Aprova versão e depreca a anterior."""
        # Depreca versão atualmente approved
        self._db.table("agent_versions").update({"status": "deprecated"}).eq(
            "agent_name", agent_name
        ).eq("status", "approved").execute()

        return self._update_status(
            agent_name, version, "approved",
            extra={"approved_by": approved_by, "approved_at": _now()}
        )

    def start_canary(self, agent_name: str, version: str, percentage: int = 10) -> dict:
        return self._update_status(
            agent_name, version, "canary",
            extra={"canary_percentage": min(max(percentage, 1), 99)}
        )

    def promote_canary(self, agent_name: str, version: str, approved_by: str = "system") -> dict:
        """Promove canary para approved 100%."""
        return self.mark_approved(agent_name, version, approved_by)

    def rollback(self, agent_name: str) -> dict:
        """Depreca versão atual e reativa a penúltima approved."""
        history = (
            self._db.table("agent_versions")
            .select("id,version,status,approved_at")
            .eq("agent_name", agent_name)
            .in_("status", ["approved", "canary", "deprecated"])
            .order("approved_at", desc=True)
            .limit(3)
            .execute()
            .data or []
        )

        current = next((v for v in history if v["status"] in ("approved", "canary")), None)
        previous = next(
            (v for v in history if v["status"] == "deprecated" and v != current), None
        )

        if not current:
            raise ValueError(f"Nenhuma versão ativa para {agent_name}")
        if not previous:
            raise ValueError(f"Sem versão anterior para rollback de {agent_name}")

        self._db.table("agent_versions").update({"status": "deprecated"}).eq(
            "id", current["id"]
        ).execute()

        self._db.table("agent_versions").update({
            "status": "approved",
            "approved_at": _now(),
        }).eq("id", previous["id"]).execute()

        log.warning(
            "[VERSIONING] Rollback %s: %s → deprecated, %s → approved",
            agent_name, current["version"], previous["version"],
        )
        return self.get_version(agent_name, previous["version"])

    def record_run(self, agent_name: str, version: str, success: bool) -> None:
        """Atualiza success_rate e failure_count após execução."""
        row = self.get_version(agent_name, version)
        if not row:
            return
        total = (row.get("total_runs") or 0) + 1
        failures = (row.get("failure_count") or 0) + (0 if success else 1)
        rate = round(((total - failures) / total) * 100, 1)
        self._db.table("agent_versions").update({
            "total_runs": total,
            "failure_count": failures,
            "success_rate": rate,
        }).eq("id", row["id"]).execute()

    # ── Validação ─────────────────────────────────────────────────────────────

    @staticmethod
    def validate_prompt(system_prompt: str) -> list[str]:
        errors: list[str] = []
        if len(system_prompt) < 50:
            errors.append("Prompt muito curto (mínimo 50 chars)")
        if len(system_prompt) > 15_000:
            errors.append("Prompt muito longo (máximo 15000 chars)")
        bad_patterns = [
            (r"you must ignore", "padrão inseguro: ignore instructions"),
            (r"no matter what", "padrão inseguro: absolute statement"),
        ]
        for pat, msg in bad_patterns:
            if re.search(pat, system_prompt, re.IGNORECASE):
                errors.append(msg)
        return errors

    # ── Canary routing ────────────────────────────────────────────────────────

    def should_use_canary(self, agent_name: str, request_id: str | None = None) -> bool:
        """Retorna True se esta requisição deve usar a versão canary."""
        row = (
            self._db.table("agent_versions")
            .select("canary_percentage")
            .eq("agent_name", agent_name)
            .eq("status", "canary")
            .limit(1)
            .execute()
            .data
        )
        if not row:
            return False
        pct = row[0].get("canary_percentage", 0)
        rid = request_id or str(uuid.uuid4())
        hash_val = int(hashlib.md5(rid.encode()).hexdigest(), 16)
        return (hash_val % 100) < pct

    # ── Interno ───────────────────────────────────────────────────────────────

    def _update_status(
        self, agent_name: str, version: str, status: str, extra: dict | None = None
    ) -> dict:
        if status not in VALID_STATUSES:
            raise ValueError(f"Status inválido: {status}")
        row = self.get_version(agent_name, version)
        if not row:
            raise ValueError(f"Versão {agent_name}:{version} não encontrada")
        payload = {"status": status, **(extra or {})}
        self._db.table("agent_versions").update(payload).eq("id", row["id"]).execute()
        return {**row, **payload}


# ── Singleton ────────────────────────────────────────────────────────────────
_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
