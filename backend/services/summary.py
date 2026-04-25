import logging
from datetime import datetime, timedelta, timezone

import httpx

from db import get_settings, get_supabase
from services.microsoft_graph import GraphClient, refresh_access_token

logger = logging.getLogger(__name__)


def _format_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except Exception:
        return iso


def _build_html(display_name: str, emails: list[dict], events: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    email_rows = ""
    if emails:
        for m in emails:
            sender = m.get("from", {}).get("emailAddress", {}).get("address", "?")
            subject = m.get("subject", "(sem assunto)")
            email_rows += f"<tr><td style='padding:4px 8px'>{sender}</td><td style='padding:4px 8px'>{subject}</td></tr>"
    else:
        email_rows = "<tr><td colspan='2' style='padding:8px;color:#6b7280'>Nenhum e-mail não lido de ontem.</td></tr>"

    event_rows = ""
    if events:
        for e in events:
            if e.get("isAllDay"):
                time_str = "Dia todo"
            else:
                start = _format_time(e.get("start", {}).get("dateTime", ""))
                end = _format_time(e.get("end", {}).get("dateTime", ""))
                time_str = f"{start} – {end}"
            subject = e.get("subject", "(sem título)")
            location = e.get("location", {}).get("displayName", "") or ""
            event_rows += f"<tr><td style='padding:4px 8px'>{time_str}</td><td style='padding:4px 8px'>{subject}</td><td style='padding:4px 8px;color:#6b7280'>{location}</td></tr>"
    else:
        event_rows = "<tr><td colspan='3' style='padding:8px;color:#6b7280'>Sem compromissos hoje.</td></tr>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;color:#111827">
  <h2 style="color:#1d4ed8">Bom dia, {display_name}! ☀️</h2>
  <p style="color:#6b7280">Resumo Moneypenny — {today}</p>
  <h3 style="margin-top:24px">📬 E-mails não lidos (ontem)</h3>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead><tr style="background:#f3f4f6">
      <th style="padding:6px 8px;text-align:left">Remetente</th>
      <th style="padding:6px 8px;text-align:left">Assunto</th>
    </tr></thead>
    <tbody>{email_rows}</tbody>
  </table>
  <h3 style="margin-top:24px">📅 Agenda de hoje</h3>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead><tr style="background:#f3f4f6">
      <th style="padding:6px 8px;text-align:left">Horário</th>
      <th style="padding:6px 8px;text-align:left">Compromisso</th>
      <th style="padding:6px 8px;text-align:left">Local</th>
    </tr></thead>
    <tbody>{event_rows}</tbody>
  </table>
  <hr style="margin-top:32px;border:none;border-top:1px solid #e5e7eb">
  <p style="font-size:12px;color:#9ca3af">Moneypenny — enviado automaticamente</p>
</body>
</html>"""


def _build_calendar_text(display_name: str, events: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    lines = [f"☀️ Bom dia, {display_name}! Sua agenda — {today}", ""]
    lines.append("📅 *Compromissos de hoje*")
    if events:
        for e in events:
            if e.get("isAllDay"):
                time_str = "Dia todo"
            else:
                start = _format_time(e.get("start", {}).get("dateTime", ""))
                end = _format_time(e.get("end", {}).get("dateTime", ""))
                time_str = f"{start} – {end}"
            subject = e.get("subject", "(sem título)")
            lines.append(f"• {time_str} — {subject}")
    else:
        lines.append("Sem compromissos hoje.")
    lines.append("")
    lines.append("_Moneypenny_")
    return "\n".join(lines)


def _build_text(display_name: str, emails: list[dict], events: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    lines = [f"☀️ Bom dia, {display_name}! Resumo Moneypenny — {today}", ""]

    lines.append("📬 *E-mails não lidos (ontem)*")
    if emails:
        for m in emails[:10]:
            sender = m.get("from", {}).get("emailAddress", {}).get("address", "?")
            subject = m.get("subject", "(sem assunto)")
            lines.append(f"• {sender} — {subject}")
    else:
        lines.append("Nenhum e-mail não lido.")

    lines.append("")
    lines.append("📅 *Agenda de hoje*")
    if events:
        for e in events:
            if e.get("isAllDay"):
                time_str = "Dia todo"
            else:
                start = _format_time(e.get("start", {}).get("dateTime", ""))
                end = _format_time(e.get("end", {}).get("dateTime", ""))
                time_str = f"{start} – {end}"
            subject = e.get("subject", "(sem título)")
            lines.append(f"• {time_str} — {subject}")
    else:
        lines.append("Sem compromissos hoje.")

    lines.append("")
    lines.append("_Moneypenny — enviado automaticamente_")
    return "\n".join(lines)


def _build_teams_payload(display_name: str, emails: list[dict], events: list[dict]) -> dict:
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    email_blocks: list[dict] = []
    for m in (emails or [])[:15]:
        sender = m.get("from", {}).get("emailAddress", {}).get("address", "?")
        subject = m.get("subject", "(sem assunto)")
        email_blocks.append({
            "type": "TextBlock",
            "text": f"**{sender}** — {subject}",
            "wrap": True,
            "spacing": "Small",
        })
    if not email_blocks:
        email_blocks = [{"type": "TextBlock", "text": "Nenhum e-mail não lido.", "isSubtle": True}]

    event_blocks: list[dict] = []
    for e in (events or []):
        if e.get("isAllDay"):
            time_str = "Dia todo"
        else:
            start = _format_time(e.get("start", {}).get("dateTime", ""))
            end = _format_time(e.get("end", {}).get("dateTime", ""))
            time_str = f"{start} – {end}"
        subject = e.get("subject", "(sem título)")
        event_blocks.append({
            "type": "TextBlock",
            "text": f"**{time_str}** — {subject}",
            "wrap": True,
            "spacing": "Small",
        })
    if not event_blocks:
        event_blocks = [{"type": "TextBlock", "text": "Sem compromissos hoje.", "isSubtle": True}]

    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.2",
        "body": [
            {"type": "TextBlock", "text": f"☀️ Bom dia, {display_name}!", "size": "Large", "weight": "Bolder"},
            {"type": "TextBlock", "text": f"Resumo Moneypenny — {today}", "isSubtle": True, "spacing": "None"},
            {"type": "TextBlock", "text": "📬 E-mails não lidos (ontem)", "weight": "Bolder", "spacing": "Large"},
            *email_blocks,
            {"type": "TextBlock", "text": "📅 Agenda de hoje", "weight": "Bolder", "spacing": "Large"},
            *event_blocks,
        ],
    }

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": card,
        }],
    }


async def send_teams(webhook_url: str, display_name: str, emails: list[dict], events: list[dict]) -> None:
    payload = _build_teams_payload(display_name, emails, events)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()


async def send_whatsapp(phone: str, display_name: str, emails: list[dict], events: list[dict]) -> None:
    s = get_settings()
    if not s.whatsapp_api_url or not s.whatsapp_instance:
        raise ValueError("WhatsApp API não configurada no servidor.")

    text = _build_text(display_name, emails, events)
    number = phone.strip().replace("+", "").replace(" ", "").replace("-", "")

    url = f"{s.whatsapp_api_url.rstrip('/')}/message/sendText/{s.whatsapp_instance}"
    # Use connect timeout curto + read timeout longo (OCI free tier pode ser lento)
    timeout = httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            url,
            json={"number": number, "text": text},
            headers={"apikey": s.whatsapp_api_key},
        )
        resp.raise_for_status()


async def run_daily_summaries() -> None:
    db = get_supabase()
    current_hour_utc = datetime.now(timezone.utc).hour

    prefs_result = (
        db.table("notification_prefs")
        .select("user_id,delivery_channel,teams_webhook_url,whatsapp_phone")
        .eq("active", True)
        .eq("send_hour_utc", current_hour_utc)
        .execute()
    )
    if not prefs_result.data:
        return

    pref_map = {p["user_id"]: p for p in prefs_result.data}
    active_user_ids = list(pref_map.keys())

    accounts = (
        db.table("connected_accounts")
        .select("*")
        .eq("provider", "microsoft")
        .in_("user_id", active_user_ids)
        .execute()
    )
    if not accounts.data:
        return

    profiles = (
        db.table("profiles")
        .select("id,display_name,email")
        .in_("id", active_user_ids)
        .execute()
    )
    profile_map = {p["id"]: p for p in profiles.data}

    for account in accounts.data:
        user_id = account["user_id"]
        profile = profile_map.get(user_id)
        pref = pref_map.get(user_id)
        if not profile or not pref:
            continue

        try:
            token_expiry = datetime.fromisoformat(account["token_expiry"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) >= token_expiry:
                refreshed = refresh_access_token(account["refresh_token"])
                new_expiry = datetime.now(timezone.utc) + timedelta(seconds=int(refreshed.get("expires_in", 3600)))
                db.table("connected_accounts").update({
                    "access_token": refreshed["access_token"],
                    "refresh_token": refreshed.get("refresh_token") or account["refresh_token"],
                    "token_expiry": new_expiry.isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", account["id"]).execute()
                access_token = refreshed["access_token"]
            else:
                access_token = account["access_token"]

            graph = GraphClient(access_token)
            emails = graph.get_unread_emails_yesterday()
            events = graph.get_today_events()

            channel = pref.get("delivery_channel") or "email"

            if channel == "teams":
                webhook_url = pref.get("teams_webhook_url") or ""
                if not webhook_url:
                    logger.warning("Teams webhook não configurado para user %s", user_id)
                    continue
                await send_teams(webhook_url, profile["display_name"], emails, events)

            elif channel == "whatsapp":
                phone = pref.get("whatsapp_phone") or ""
                if not phone:
                    logger.warning("Telefone WhatsApp não configurado para user %s", user_id)
                    continue
                await send_whatsapp(phone, profile["display_name"], emails, events)

            else:
                html = _build_html(profile["display_name"], emails, events)
                graph.send_mail(
                    to_address=account["email"],
                    subject=f"☀️ Resumo do dia — {datetime.now(timezone.utc).strftime('%d/%m/%Y')}",
                    html_body=html,
                )

            logger.info("Summary (%s) sent for user %s", channel, user_id)

        except Exception:
            logger.exception("Failed to send summary for user %s", user_id)
