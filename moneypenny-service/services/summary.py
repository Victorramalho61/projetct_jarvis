import logging
from datetime import datetime, timedelta, timezone
from html import escape as _esc

import httpx

from db import get_settings, get_supabase
from services.microsoft_graph import GraphClient, get_access_token

_BRT = timezone(timedelta(hours=-3))

_DAYS_PT = {
    "Monday": "Segunda-feira", "Tuesday": "Terça-feira", "Wednesday": "Quarta-feira",
    "Thursday": "Quinta-feira", "Friday": "Sexta-feira", "Saturday": "Sábado", "Sunday": "Domingo",
}

_MOTIVATIONAL = {
    "Monday":    "Semana nova, energia nova. Vai com tudo! 🚀",
    "Tuesday":   "Foco total — o trabalho de hoje constrói o amanhã. 💡",
    "Wednesday": "Meio da semana, ritmo de chegada. Não para agora! ⚡",
    "Thursday":  "Reta final da semana. Cada hora conta. 🎯",
    "Friday":    "Sexta-feira! Feche tudo com chave de ouro. 🏆",
    "Saturday":  "Fim de semana com propósito é tempo bem gasto. 🌟",
    "Sunday":    "Descanse, recarregue e prepare-se para o que vem. 🌿",
}

logger = logging.getLogger(__name__)


def _format_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_BRT).strftime("%H:%M")
    except Exception:
        return iso


def _clean_preview(text: str) -> str:
    """Retorna a primeira linha útil do bodyPreview, sem lixo de separadores."""
    if not text:
        return ""
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if len(line) > 15 and not all(c in "-_=* \t" for c in line):
            return (_esc(line[:130]) + "…") if len(line) > 130 else _esc(line)
    return ""


def _build_html(display_name: str, emails: list[dict], events: list[dict]) -> str:
    now_local = datetime.now(_BRT)
    today = now_local.strftime("%d/%m/%Y")
    eng_day = now_local.strftime("%A")
    weekday = _DAYS_PT.get(eng_day, eng_day)
    phrase = _MOTIVATIONAL.get(eng_day, "Tenha um ótimo dia!")

    event_count = len(events)
    email_count = len(emails)

    # --- Eventos ---
    events_html = ""
    if events:
        for e in events:
            if e.get("isAllDay"):
                time_str = "Dia todo"
                time_color = "#0D3664"
            else:
                t_s = _format_time(e.get("start", {}).get("dateTime", ""))
                t_e = _format_time(e.get("end", {}).get("dateTime", ""))
                time_str = f"{t_s} – {t_e}"
                time_color = "#00694E"

            subject   = _esc(e.get("subject") or "(sem título)")
            location  = _esc((e.get("location") or {}).get("displayName") or "")
            organizer = _esc((e.get("organizer") or {}).get("emailAddress", {}).get("name") or "")
            is_online = e.get("isOnlineMeeting", False)
            meeting_url = e.get("onlineMeetingUrl") or ""
            preview   = _clean_preview(e.get("bodyPreview") or "")

            response = (e.get("responseStatus") or {}).get("response", "")
            if response == "accepted":
                badge = '<span style="background:#e0f0eb;color:#00694E;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">✓ Confirmado</span>'
            elif response == "tentativelyAccepted":
                badge = '<span style="background:#fdf3e0;color:#DC9001;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">⏳ Talvez</span>'
            elif response == "notResponded":
                badge = '<span style="background:#EFEEF5;color:#6b7280;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">Pendente</span>'
            else:
                badge = ""

            meta_parts = []
            if organizer:
                meta_parts.append(f"👤 {organizer}")
            if location:
                meta_parts.append(f"📍 {location}")
            if is_online:
                if meeting_url:
                    meta_parts.append(f'<a href="{_esc(meeting_url)}" style="color:#00694E;text-decoration:none;font-weight:600">🖥 Entrar na reunião</a>')
                else:
                    meta_parts.append("🖥 Online")

            meta_html = (
                f'<div style="font-size:13px;color:#6b7280;margin-top:5px">'
                f'{"&nbsp; · &nbsp;".join(meta_parts)}</div>'
            ) if meta_parts else ""

            badge_html = (
                f'<div style="margin-top:6px">{badge}</div>'
            ) if badge else ""

            preview_html = (
                f'<div style="font-size:12px;color:#9ca3af;margin-top:6px;font-style:italic">{preview}</div>'
            ) if preview else ""

            events_html += f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:4px">
          <tr>
            <td width="110" valign="top" style="padding:0 16px 16px 0">
              <div style="font-weight:700;font-size:13px;color:{time_color};white-space:nowrap">{time_str}</div>
              {badge_html}
            </td>
            <td valign="top" style="padding-bottom:16px;border-bottom:1px solid #f3f4f6">
              <div style="font-weight:600;font-size:15px;color:#131516">{subject}</div>
              {meta_html}
              {preview_html}
            </td>
          </tr>
        </table>"""
    else:
        events_html = '<p style="color:#9ca3af;font-size:14px;text-align:center;padding:16px 0;margin:0">Nenhum compromisso agendado para hoje.</p>'

    # --- E-mails ---
    emails_html = ""
    if emails:
        for m in emails[:15]:
            from_obj    = (m.get("from") or {}).get("emailAddress") or {}
            sender_name = _esc(from_obj.get("name") or from_obj.get("address", "?"))
            sender_addr = _esc(from_obj.get("address", ""))
            subject     = _esc(m.get("subject") or "(sem assunto)")
            emails_html += f"""
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:9px 0;border-bottom:1px solid #f9fafb">
              <div style="font-weight:600;font-size:14px;color:#131516">{sender_name}</div>
              <div style="font-size:11px;color:#9ca3af;margin-top:1px">{sender_addr}</div>
              <div style="font-size:13px;color:#131516;margin-top:3px">{subject}</div>
            </td>
          </tr>
        </table>"""
        if len(emails) > 15:
            extra = len(emails) - 15
            emails_html += f'<p style="font-size:13px;color:#6b7280;margin:8px 0 0">…e mais {extra} e-mail{"s" if extra > 1 else ""}</p>'
    else:
        emails_html = '<p style="color:#9ca3af;font-size:14px;text-align:center;padding:16px 0;margin:0">Nenhum e-mail não lido de ontem.</p>'

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Resumo do dia — {today}</title>
</head>
<body style="margin:0;padding:0;background:#EFEEF5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#EFEEF5">
    <tr><td style="padding:32px 16px" align="center">

      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(13,54,100,0.12)">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#0D3664 0%,#00694E 100%);padding:32px 32px 28px">
            <div style="color:#a8d5c5;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">Moneypenny · Jarvis</div>
            <div style="color:#ffffff;font-size:27px;font-weight:700;line-height:1.2">☀️ Bom dia, {_esc(display_name)}!</div>
            <div style="color:#a8d5c5;font-size:15px;margin-top:8px">{weekday}, {today}</div>
          </td>
        </tr>

        <!-- Frase motivacional -->
        <tr>
          <td style="background:#e0f0eb;padding:14px 32px;border-bottom:2px solid #00694E">
            <div style="color:#00694E;font-size:14px;font-style:italic">{phrase}</div>
          </td>
        </tr>

        <!-- Stats -->
        <tr>
          <td style="padding:20px 32px;border-bottom:2px solid #EFEEF5">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="text-align:center;padding:8px 0">
                  <div style="font-size:28px;font-weight:700;color:#00694E">{event_count}</div>
                  <div style="font-size:11px;color:#6b7280;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;margin-top:2px">Compromisso{"s" if event_count != 1 else ""}</div>
                </td>
                <td width="1" style="background:#EFEEF5"></td>
                <td style="text-align:center;padding:8px 0">
                  <div style="font-size:28px;font-weight:700;color:#0D3664">{email_count}</div>
                  <div style="font-size:11px;color:#6b7280;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;margin-top:2px">E-mail{"s" if email_count != 1 else ""} não lido{"s" if email_count != 1 else ""}</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Agenda -->
        <tr>
          <td style="padding:28px 32px 12px">
            <div style="font-size:11px;font-weight:700;color:#0D3664;letter-spacing:1px;text-transform:uppercase;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #00694E">📅 Agenda de hoje</div>
            {events_html}
          </td>
        </tr>

        <!-- E-mails -->
        <tr>
          <td style="padding:12px 32px 12px">
            <div style="font-size:11px;font-weight:700;color:#0D3664;letter-spacing:1px;text-transform:uppercase;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #00694E">📬 E-mails não lidos (ontem)</div>
            {emails_html}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 32px;background:#0D3664;border-top:3px solid #DC9001">
            <div style="font-size:12px;color:#a8d5c5;text-align:center">
              Enviado automaticamente &nbsp;·&nbsp; <strong style="color:#ffffff">Moneypenny by Voetur Jarvis</strong>
            </div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _build_calendar_text(display_name: str, events: list[dict]) -> str:
    now_local = datetime.now(_BRT)
    today = now_local.strftime("%d/%m/%Y")
    eng_day = now_local.strftime("%A")
    weekday = _DAYS_PT.get(eng_day, eng_day)
    phrase = _MOTIVATIONAL.get(eng_day, "Tenha um ótimo dia! 💼")

    lines = [f"☀️ *Bom dia, {display_name}!*", f"{weekday}, {today}", ""]
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
            location = (e.get("location") or {}).get("displayName") or ""
            organizer = (e.get("organizer") or {}).get("emailAddress", {}).get("name") or ""
            lines.append(f"• {time_str} — {subject}")
            meta: list[str] = []
            if organizer:
                meta.append(f"👤 {organizer}")
            if location:
                meta.append(f"📍 {location}")
            if meta:
                lines.append(f"  _{'  ·  '.join(meta)}_")
    else:
        lines.append("Sem compromissos hoje. Aproveite o dia! 🌿")
    lines.append("")
    lines.append(phrase)
    lines.append("_by Voetur Jarvis_")
    return "\n".join(lines)


def _build_text(display_name: str, emails: list[dict], events: list[dict]) -> str:
    today = datetime.now(_BRT).strftime("%d/%m/%Y")
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
    today = datetime.now(_BRT).strftime("%d/%m/%Y")

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


def _build_teams_chat_html(display_name: str, emails: list[dict], events: list[dict]) -> str:
    brt_now = datetime.now(_BRT)
    today = brt_now.strftime("%d/%m/%Y")
    eng_day = brt_now.strftime("%A")
    weekday = _DAYS_PT.get(eng_day, eng_day)

    html = f"<strong>☀️ Bom dia, {_esc(display_name)}!</strong> &nbsp;·&nbsp; {weekday}, {today}<br><br>"

    html += "<strong>📅 Agenda de hoje</strong><ul>"
    if events:
        for e in events[:15]:
            if e.get("isAllDay"):
                time_str = "Dia todo"
            else:
                ts = _format_time(e.get("start", {}).get("dateTime", ""))
                te = _format_time(e.get("end", {}).get("dateTime", ""))
                time_str = f"{ts}&nbsp;–&nbsp;{te}"
            subject = _esc(e.get("subject") or "(sem título)")
            html += f"<li>{time_str} — {subject}</li>"
    else:
        html += "<li><em>Sem compromissos hoje.</em></li>"
    html += "</ul>"

    html += "<br><strong>📬 E-mails não lidos (ontem)</strong><ul>"
    if emails:
        for m in emails[:10]:
            from_obj = (m.get("from") or {}).get("emailAddress") or {}
            sender = _esc(from_obj.get("name") or from_obj.get("address", "?"))
            subject = _esc(m.get("subject") or "(sem assunto)")
            html += f"<li><strong>{sender}</strong> — {subject}</li>"
        if len(emails) > 10:
            html += f"<li><em>…e mais {len(emails) - 10} e-mail(s)</em></li>"
    else:
        html += "<li><em>Nenhum e-mail não lido.</em></li>"
    html += "</ul>"

    html += "<br><em>Moneypenny by Voetur Jarvis</em>"
    return html


async def send_teams_direct(graph: GraphClient, chat_id: str, display_name: str, emails: list[dict], events: list[dict]) -> None:
    html = _build_teams_chat_html(display_name, emails, events)
    await graph.send_teams_chat_message_async(chat_id, html)


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
        .select("user_id,channels_config,teams_webhook_url,teams_chat_id,teams_mode,whatsapp_phone")
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
            access_token = get_access_token(account, db)
            graph = GraphClient(access_token)
            channels: dict = pref.get("channels_config") or {}
            enabled = {k: v for k, v in channels.items() if v.get("enabled")}

            if not enabled:
                logger.info("Nenhum canal habilitado para user %s, pulando", user_id)
                continue

            emails_data: list[dict] | None = None
            events_data: list[dict] | None = None

            for ch_name, ch_cfg in enabled.items():
                content = ch_cfg.get("content", [])
                needs_emails = "emails" in content
                needs_events = "calendar" in content

                if needs_emails and emails_data is None:
                    emails_data = graph.get_unread_emails_yesterday()
                if needs_events and events_data is None:
                    events_data = graph.get_today_events()

                emails_out = emails_data if needs_emails else []
                events_out = events_data if needs_events else []

                if ch_name == "email":
                    html = _build_html(profile["display_name"], emails_out, events_out)
                    graph.send_mail(
                        to_address=account["email"],
                        subject=f"☀️ Resumo do dia — {datetime.now(_BRT).strftime('%d/%m/%Y')}",
                        html_body=html,
                    )

                elif ch_name == "teams":
                    teams_mode = pref.get("teams_mode") or "webhook"
                    if teams_mode == "direct":
                        chat_id = pref.get("teams_chat_id") or ""
                        if not chat_id:
                            logger.warning("Chat Teams direto não inicializado para user %s", user_id)
                            continue
                        await send_teams_direct(graph, chat_id, profile["display_name"], emails_out, events_out)
                    else:
                        webhook_url = pref.get("teams_webhook_url") or ""
                        if not webhook_url:
                            logger.warning("Teams webhook não configurado para user %s", user_id)
                            continue
                        await send_teams(webhook_url, profile["display_name"], emails_out, events_out)

                elif ch_name == "whatsapp":
                    phone = pref.get("whatsapp_phone") or ""
                    if not phone:
                        logger.warning("Telefone WhatsApp não configurado para user %s", user_id)
                        continue
                    await send_whatsapp(phone, profile["display_name"], emails_out, events_out)

            logger.info("Summary sent via %s for user %s", list(enabled.keys()), user_id)

        except Exception:
            logger.exception("Failed to send summary for user %s", user_id)
