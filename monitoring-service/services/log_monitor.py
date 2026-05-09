import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import httpx

from db import get_settings, get_supabase

logger = logging.getLogger(__name__)

_REPO = "Victorramalho61/projetct_jarvis"
_RECURRING_THRESHOLD = 3
_CRITICAL_THRESHOLD = 5
_GROWTH_THRESHOLD = 0.80  # 80% de crescimento dispara alerta


async def run_error_growth_check() -> None:
    """Compara contagem de erros por módulo nas últimas 24h vs 24-48h atrás.
    Se crescimento ≥ 80%, cria issue no GitHub e envia WhatsApp."""
    s = get_settings()
    if not s.github_token:
        return

    db = get_supabase()
    now = datetime.now(timezone.utc)
    cutoff_recent = (now - timedelta(hours=24)).isoformat()
    cutoff_prev = (now - timedelta(hours=48)).isoformat()

    recent_result = (
        db.table("app_logs")
        .select("module,level")
        .eq("level", "error")
        .gte("created_at", cutoff_recent)
        .limit(2000)
        .execute()
    )
    prev_result = (
        db.table("app_logs")
        .select("module,level")
        .eq("level", "error")
        .gte("created_at", cutoff_prev)
        .lt("created_at", cutoff_recent)
        .limit(2000)
        .execute()
    )

    recent_counts: Counter = Counter(r["module"] for r in (recent_result.data or []))
    prev_counts: Counter = Counter(r["module"] for r in (prev_result.data or []))

    growing = []
    for module, count_now in recent_counts.items():
        count_before = prev_counts.get(module, 0)
        if count_before == 0:
            continue
        growth = (count_now - count_before) / count_before
        if growth >= _GROWTH_THRESHOLD:
            growing.append((module, count_before, count_now, growth))

    if not growing:
        logger.info("Growth check: nenhum módulo com crescimento ≥ %d%%", int(_GROWTH_THRESHOLD * 100))
        return

    growing.sort(key=lambda x: x[3], reverse=True)
    logger.warning("Growth check: %d módulo(s) com crescimento acelerado de erros", len(growing))

    date_str = now.astimezone(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M")
    rows = "\n".join(
        f"| `{m}` | {c_prev} | {c_now} | **+{growth:.0%}** |"
        for m, c_prev, c_now, growth in growing
    )
    body = (
        f"## Crescimento acelerado de erros — {date_str}\n\n"
        f"Módulos com aumento ≥ {int(_GROWTH_THRESHOLD * 100)}% nas últimas 24h vs período anterior:\n\n"
        f"| Módulo | Erros (24-48h) | Erros (0-24h) | Crescimento |\n"
        f"|--------|---------------|--------------|-------------|\n"
        f"{rows}\n\n"
        f"---\n*Gerado automaticamente pelo growth-monitor do Jarvis.*"
    )
    title = f"[Growth-Monitor] Crescimento de erros detectado — {date_str}"
    headers = {
        "Authorization": f"token {s.github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{_REPO}/issues",
            headers=headers,
            json={"title": title, "body": body, "labels": ["bug", "auto-monitor", "growth-alert"]},
        )
        if resp.is_success:
            logger.info("Growth check: issue criada — #%d", resp.json()["number"])
        else:
            logger.error("Growth check: falha ao criar issue — %s", resp.text)



async def run_log_monitor() -> None:
    s = get_settings()
    if not s.github_token:
        logger.warning("GITHUB_TOKEN não configurado — log monitor ignorado")
        return

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    db = get_supabase()
    result = (
        db.table("app_logs")
        .select("level,module,message,detail,created_at")
        .in_("level", ["error", "warning"])
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )
    logs = result.data or []
    logger.info("Log monitor: %d entradas de erro/warning nas últimas 24h", len(logs))

    if not logs:
        return

    pattern_counts: Counter = Counter((r["module"], r["message"]) for r in logs)
    recurring = [
        (module, msg, count)
        for (module, msg), count in pattern_counts.most_common()
        if count >= _RECURRING_THRESHOLD
    ]

    if not recurring:
        logger.info("Log monitor: nenhum padrão recorrente (limiar: %d)", _RECURRING_THRESHOLD)
        return

    logger.warning("Log monitor: %d padrão(ões) recorrente(s) encontrado(s)", len(recurring))
    await _create_or_update_github_issue(s.github_token, recurring, logs)

    critical = [(m, msg, c) for m, msg, c in recurring if c >= _CRITICAL_THRESHOLD]


async def _create_or_update_github_issue(
    token: str,
    recurring: list[tuple[str, str, int]],
    all_logs: list[dict],
) -> None:
    date_str = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")
    title = f"[Auto-Monitor] Erros recorrentes detectados — {date_str}"

    rows = "\n".join(
        f"| `{m}` | {msg[:80]} | **{c}x** |"
        for m, msg, c in recurring
    )

    by_module: dict[str, list] = defaultdict(list)
    for entry in all_logs:
        by_module[entry["module"]].append(entry)

    details_sections = []
    for module, msg, count in recurring[:5]:
        samples = [
            e for e in by_module.get(module, [])
            if e["message"] == msg
        ][:3]
        sample_lines = "\n".join(
            f"  - `{s['created_at'][:19]}` {s.get('detail') or ''}"
            for s in samples
        )
        details_sections.append(
            f"### `{module}` — {msg[:100]}\n"
            f"Ocorrências: **{count}**\n"
            f"Amostras:\n{sample_lines}"
        )

    body = (
        f"## Relatório automático de erros — {date_str}\n\n"
        f"**Total de eventos (erro/warning, últimas 24h):** {len(all_logs)}\n\n"
        f"### Padrões recorrentes (≥ {_RECURRING_THRESHOLD} ocorrências)\n\n"
        f"| Módulo | Mensagem | Ocorrências |\n"
        f"|--------|----------|-------------|\n"
        f"{rows}\n\n"
        + "\n\n".join(details_sections)
        + "\n\n---\n*Gerado automaticamente pelo log-monitor do Jarvis.*"
    )

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        # Check for existing open issue from today
        search_resp = await client.get(
            f"https://api.github.com/repos/{_REPO}/issues",
            headers=headers,
            params={"state": "open", "labels": "auto-monitor", "per_page": 10},
        )
        existing = [
            i for i in (search_resp.json() if search_resp.is_success else [])
            if date_str in i.get("title", "")
        ]

        if existing:
            issue_number = existing[0]["number"]
            await client.post(
                f"https://api.github.com/repos/{_REPO}/issues/{issue_number}/comments",
                headers=headers,
                json={"body": f"**Atualização {datetime.now(timezone(timedelta(hours=-3))).strftime('%H:%M')}:**\n\n{body}"},
            )
            logger.info("Log monitor: comentário adicionado à issue #%d", issue_number)
        else:
            resp = await client.post(
                f"https://api.github.com/repos/{_REPO}/issues",
                headers=headers,
                json={
                    "title": title,
                    "body": body,
                    "labels": ["bug", "auto-monitor"],
                },
            )
            if resp.is_success:
                issue = resp.json()
                logger.info("Log monitor: issue criada — #%d %s", issue["number"], issue["html_url"])
            else:
                logger.error("Log monitor: falha ao criar issue — %s", resp.text)


async def _send_whatsapp_alert(s, critical: list[tuple[str, str, int]]) -> None:
    db = get_supabase()
    admins = (
        db.table("profiles")
        .select("whatsapp_phone,display_name")
        .eq("role", "admin")
        .eq("active", True)
        .neq("whatsapp_phone", "")
        .execute()
    )

    if not admins.data:
        return

    lines = "\n".join(f"• [{m}] {msg[:60]} ({c}x)" for m, msg, c in critical)
    text = (
        f"⚠️ *JARVIS — Alerta de erros críticos*\n\n"
        f"{lines}\n\n"
        f"Acesse o GitHub para ver a issue aberta automaticamente."
    )

    async with httpx.AsyncClient(timeout=10) as client:
        for admin in admins.data:
            phone = admin["whatsapp_phone"]
            if not phone:
                continue
            try:
                await client.post(
                    f"{s.whatsapp_api_url}/message/sendText/{s.whatsapp_instance}",
                    headers={"apikey": s.whatsapp_api_key},
                    json={"number": phone, "text": text},
                )
            except Exception as exc:
                logger.warning("Falha ao enviar WhatsApp para %s: %s", phone, exc)
