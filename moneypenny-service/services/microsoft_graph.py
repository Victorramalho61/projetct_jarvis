from datetime import datetime, timedelta, timezone

import httpx
import msal

from db import get_settings

_SCOPES = [
    "User.Read",
    "Mail.Read",
    "Calendars.Read",
    "Mail.Send",
]


def _build_msal_app() -> msal.ConfidentialClientApplication:
    s = get_settings()
    authority = f"https://login.microsoftonline.com/{s.microsoft_tenant_id}"
    return msal.ConfidentialClientApplication(
        s.microsoft_client_id,
        authority=authority,
        client_credential=s.microsoft_client_secret,
    )


def build_auth_url(state: str) -> str:
    s = get_settings()
    app = _build_msal_app()
    return app.get_authorization_request_url(
        scopes=_SCOPES,
        state=state,
        redirect_uri=s.microsoft_redirect_uri,
    )


def exchange_code_for_tokens(code: str) -> dict:
    s = get_settings()
    app = _build_msal_app()
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=_SCOPES,
        redirect_uri=s.microsoft_redirect_uri,
    )
    if "error" in result:
        raise ValueError(result.get("error_description", result["error"]))
    return result


def refresh_access_token(refresh_token: str) -> dict:
    app = _build_msal_app()
    result = app.acquire_token_by_refresh_token(
        refresh_token=refresh_token,
        scopes=_SCOPES,
    )
    if "error" in result:
        raise ValueError(result.get("error_description", result["error"]))
    return result


class GraphClient:
    BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, access_token: str):
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        with httpx.Client(timeout=20) as client:
            r = client.get(f"{self.BASE}{path}", headers=self._headers, params=params)
            r.raise_for_status()
            return r.json()

    def _post(self, path: str, body: dict) -> dict | None:
        with httpx.Client(timeout=20) as client:
            r = client.post(f"{self.BASE}{path}", headers=self._headers, json=body)
            r.raise_for_status()
            return r.json() if r.content else None

    def get_me(self) -> dict:
        return self._get("/me", params={"$select": "displayName,mail,userPrincipalName"})

    _NOREPLY_PATTERNS = (
        "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply",
        "do_not_reply", "mailer-daemon", "mailer_daemon", "notifications@",
        "notification@", "automated@", "automailer@", "bounce@",
    )

    def _is_automated(self, email: dict) -> bool:
        addr = email.get("from", {}).get("emailAddress", {}).get("address", "").lower()
        return any(p in addr for p in self._NOREPLY_PATTERNS)

    def get_unread_emails_yesterday(self) -> list[dict]:
        from datetime import datetime, timedelta, timezone

        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

        data = self._get(
            "/me/messages",
            params={
                "$filter": f"isRead eq false and receivedDateTime ge {yesterday} and receivedDateTime lt {today}",
                "$select": "subject,from,receivedDateTime",
                "$top": "50",
                "$orderby": "receivedDateTime desc",
            },
        )
        emails = data.get("value", [])
        return [e for e in emails if not self._is_automated(e)]

    def get_today_events(self) -> list[dict]:
        BRT = timezone(timedelta(hours=-3))
        now_local = datetime.now(BRT)
        day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = now_local.replace(hour=23, minute=59, second=59, microsecond=0)
        start = day_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = day_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        data = self._get(
            "/me/calendarView",
            params={
                "startDateTime": start,
                "endDateTime": end,
                "$select": "subject,start,end,location,isAllDay,organizer,responseStatus,isOnlineMeeting,onlineMeetingUrl,bodyPreview",
                "$orderby": "start/dateTime",
                "$top": "20",
            },
        )
        return data.get("value", [])

    def send_mail(self, to_address: str, subject: str, html_body: str) -> None:
        self._post(
            "/me/sendMail",
            {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": html_body},
                    "toRecipients": [{"emailAddress": {"address": to_address}}],
                },
                "saveToSentItems": True,
            },
        )


def get_access_token(account: dict, db) -> str:
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
        return refreshed["access_token"]
    return account["access_token"]
