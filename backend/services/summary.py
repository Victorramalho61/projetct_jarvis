import logging
from datetime import datetime, timedelta, timezone

from db import get_supabase
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

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;color:#111827">
  <h2 style="color:#1d4ed8">Bom dia, {display_name}! ☀️</h2>
  <p style="color:#6b7280">Resumo Moneypenny — {today}</p>

  <h3 style="margin-top:24px">📬 E-mails não lidos (ontem)</h3>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead>
      <tr style="background:#f3f4f6">
        <th style="padding:6px 8px;text-align:left">Remetente</th>
        <th style="padding:6px 8px;text-align:left">Assunto</th>
      </tr>
    </thead>
    <tbody>{email_rows}</tbody>
  </table>

  <h3 style="margin-top:24px">📅 Agenda de hoje</h3>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead>
      <tr style="background:#f3f4f6">
        <th style="padding:6px 8px;text-align:left">Horário</th>
        <th style="padding:6px 8px;text-align:left">Compromisso</th>
        <th style="padding:6px 8px;text-align:left">Local</th>
      </tr>
    </thead>
    <tbody>{event_rows}</tbody>
  </table>

  <hr style="margin-top:32px;border:none;border-top:1px solid #e5e7eb">
  <p style="font-size:12px;color:#9ca3af">Moneypenny — enviado automaticamente</p>
</body>
</html>
"""


async def run_daily_summaries() -> None:
    db = get_supabase()

    current_hour_utc = datetime.now(timezone.utc).hour

    prefs = (
        db.table("notification_prefs")
        .select("user_id")
        .eq("active", True)
        .eq("send_hour_utc", current_hour_utc)
        .execute()
    )
    if not prefs.data:
        return

    active_user_ids = [p["user_id"] for p in prefs.data]

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
        if not profile:
            continue

        try:
            token_expiry = datetime.fromisoformat(account["token_expiry"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) >= token_expiry:
                refreshed = refresh_access_token(account["refresh_token"])
                from datetime import timedelta
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
            html = _build_html(profile["display_name"], emails, events)
            graph.send_mail(
                to_address=account["email"],
                subject=f"☀️ Resumo do dia — {datetime.now(timezone.utc).strftime('%d/%m/%Y')}",
                html_body=html,
            )
            logger.info("Summary sent to %s", profile["email"])

        except Exception:
            logger.exception("Failed to send summary for user %s", user_id)
