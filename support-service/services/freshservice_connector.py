import logging
import time

import httpx

from db import get_settings

logger = logging.getLogger(__name__)

BASE_URL = "https://voetur1.freshservice.com/api/v2"
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 0.3


class FreshserviceConnector:
    def __init__(self) -> None:
        s = get_settings()
        self._auth = (s.freshservice_api_key, "X")

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{BASE_URL}{path}"
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=30, auth=self._auth) as client:
                    r = client.get(url, params=params)
                    if r.status_code == 429:
                        time.sleep(2 ** (attempt + 1))
                        continue
                    r.raise_for_status()
                    time.sleep(RATE_LIMIT_DELAY)
                    return r.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500 or attempt >= MAX_RETRIES - 1:
                    raise
                time.sleep(2 ** attempt)
            except httpx.RequestError:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
        return {}

    def _post(self, path: str, body: dict) -> dict:
        url = f"{BASE_URL}{path}"
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=30, auth=self._auth) as client:
                    r = client.post(url, json=body)
                    if r.status_code == 429:
                        time.sleep(2 ** (attempt + 1))
                        continue
                    r.raise_for_status()
                    time.sleep(RATE_LIMIT_DELAY)
                    return r.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500 or attempt >= MAX_RETRIES - 1:
                    raise
                time.sleep(2 ** attempt)
            except httpx.RequestError:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
        return {}

    def search_requester_by_email(self, email: str) -> dict | None:
        """Busca por e-mail em requesters e, como fallback, em agents."""
        try:
            data = self._get("/requesters", {"query": f"\"primary_email:'{email}'\"", "per_page": 1})
            requesters = data.get("requesters", [])
            if requesters:
                r = requesters[0]
                return {
                    "id": r.get("id"),
                    "name": (r.get("first_name", "") + " " + (r.get("last_name") or "")).strip(),
                    "primary_email": r.get("primary_email", ""),
                    "location_name": r.get("location_name"),
                    "department_names": r.get("department_names", []),
                }
        except Exception as exc:
            logger.error("search_requester_by_email error: %s", exc)
            return None

        # Fallback: agents (admins/support staff also open tickets)
        try:
            data = self._get("/agents", {"query": f"\"email:'{email}'\"", "per_page": 1})
            agents = data.get("agents", [])
            if not agents:
                return None
            a = agents[0]
            location_name = self._resolve_location(a.get("location_id"))
            dept_names = [self._resolve_department(d) for d in (a.get("department_ids") or [])]
            return {
                "id": a.get("id"),
                "name": (a.get("first_name", "") + " " + (a.get("last_name") or "")).strip(),
                "primary_email": a.get("email", ""),
                "location_name": location_name,
                "department_names": [d for d in dept_names if d],
            }
        except Exception as exc:
            logger.error("search_agent_by_email error: %s", exc)
            return None

    def _resolve_location(self, location_id: int | None) -> str | None:
        if not location_id:
            return None
        try:
            return self._get(f"/locations/{location_id}").get("location", {}).get("name")
        except Exception:
            return None

    def _resolve_department(self, dept_id: int) -> str | None:
        try:
            return self._get(f"/departments/{dept_id}").get("department", {}).get("name")
        except Exception:
            return None

    def create_ticket(
        self,
        subject: str,
        description: str,
        email: str,
        workspace_id: int,
        empresa: str = "",
    ) -> dict:
        body: dict = {
            "subject": subject,
            "description": description,
            "email": email,
            "workspace_id": workspace_id,
            "source": 1,
            "status": 2,
            "priority": 2,
        }
        if empresa:
            body["custom_fields"] = {"empresa": empresa}
        return self._post("/tickets", body)

    def get_tickets_by_requester(self, email: str, workspace_id: int | None = None) -> list[dict]:
        try:
            params: dict = {"query": f"\"email:'{email}' AND status:2\"", "per_page": 10}
            if workspace_id is not None:
                params["workspace_id"] = workspace_id
            return self._get("/tickets/filter", params).get("tickets", [])
        except Exception as exc:
            logger.error("get_tickets_by_requester error: %s", exc)
            return []

    def get_ticket(self, ticket_id: int) -> dict:
        try:
            return self._get(f"/tickets/{ticket_id}").get("ticket", {})
        except Exception as exc:
            logger.error("get_ticket error: %s", exc)
            return {}
