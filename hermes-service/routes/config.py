import copy
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends

from auth import require_role

router = APIRouter(prefix="/api/hermes")

CONFIG_PATH = Path("/root/.hermes/config.yaml")

AVAILABLE_TOOLSETS = [
    "web_search", "terminal", "files", "code_execution",
    "browser", "github", "docker", "database",
]

PROVIDERS = {
    "anthropic": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-7"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "groq": ["llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768"],
    "openrouter": ["auto"],
    "ollama": ["llama3", "mistral", "phi3"],
}

STREAMING_MODES = ["auto", "draft", "edit", "off"]
SESSION_MODES = ["daily", "idle", "both", "none"]

DEFAULT_CONFIG: dict[str, Any] = {
    "model": "claude-sonnet-4-6",
    "provider": "anthropic",
    "max_iterations": 10,
    "enabled_toolsets": ["web_search"],
    "platforms": {
        "telegram":  {"enabled": False, "token": "", "chat_id": ""},
        "discord":   {"enabled": False, "token": "", "chat_id": ""},
        "slack":     {"enabled": False, "token": "", "chat_id": ""},
        "whatsapp":  {"enabled": False, "token": "", "chat_id": ""},
        "signal":    {"enabled": False, "token": "", "chat_id": ""},
        "email":     {"enabled": False, "address": "", "password": ""},
    },
    "session_reset_mode": "daily",
    "session_reset_hour": 2,
    "streaming_mode": "auto",
}

_MASK = "***"


# ── Format converters ─────────────────────────────────────────────────────────

def _to_hermes(cfg: dict[str, Any]) -> dict[str, Any]:
    """Convert flat internal config to Hermes native YAML format."""
    out: dict[str, Any] = {
        "model": {
            "default": cfg.get("model", DEFAULT_CONFIG["model"]),
            "provider": cfg.get("provider", DEFAULT_CONFIG["provider"]),
        },
        "max_iterations": cfg.get("max_iterations", 10),
        "enabled_toolsets": cfg.get("enabled_toolsets", ["web_search"]),
        "session_policies": {
            "reset_policy": {
                "mode": cfg.get("session_reset_mode", "daily"),
                "hour": cfg.get("session_reset_hour", 2),
            }
        },
        "streaming_config": {"mode": cfg.get("streaming_mode", "auto")},
        "platforms": {},
    }
    for platform, pcfg in cfg.get("platforms", {}).items():
        if platform == "email":
            out["platforms"][platform] = {
                "enabled": pcfg.get("enabled", False),
                "address": pcfg.get("address", ""),
                "password": pcfg.get("password", ""),
            }
        else:
            hp: dict[str, Any] = {
                "enabled": pcfg.get("enabled", False),
                "token": pcfg.get("token", ""),
            }
            chat_id = str(pcfg.get("chat_id", "")).strip()
            if chat_id:
                hp["home_channel"] = {"platform": platform, "chat_id": chat_id}
            out["platforms"][platform] = hp
    return out


def _from_hermes(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse Hermes native format back to flat internal format."""
    session = raw.get("session_policies", {}).get("reset_policy", {})
    streaming = raw.get("streaming_config", {})
    raw_model = raw.get("model", DEFAULT_CONFIG["model"])
    if isinstance(raw_model, dict):
        model = raw_model.get("default", DEFAULT_CONFIG["model"])
        provider = raw_model.get("provider", DEFAULT_CONFIG["provider"])
    else:
        model = raw_model
        provider = raw.get("provider", DEFAULT_CONFIG["provider"])
    cfg: dict[str, Any] = {
        "model": model,
        "provider": provider,
        "max_iterations": raw.get("max_iterations", 10),
        "enabled_toolsets": raw.get("enabled_toolsets", ["web_search"]),
        "session_reset_mode": session.get("mode", "daily"),
        "session_reset_hour": session.get("hour", 2),
        "streaming_mode": streaming.get("mode", "auto"),
        "platforms": {},
    }
    for platform, pcfg in raw.get("platforms", {}).items():
        if platform == "email":
            cfg["platforms"][platform] = {
                "enabled": pcfg.get("enabled", False),
                "address": pcfg.get("address", ""),
                "password": pcfg.get("password", ""),
            }
        else:
            home = pcfg.get("home_channel", {})
            chat_id = home.get("chat_id", pcfg.get("chat_id", ""))
            cfg["platforms"][platform] = {
                "enabled": pcfg.get("enabled", False),
                "token": pcfg.get("token", ""),
                "chat_id": str(chat_id) if chat_id else "",
            }
    for p, defaults in DEFAULT_CONFIG["platforms"].items():
        cfg["platforms"].setdefault(p, copy.deepcopy(defaults))
    return cfg


# ── Storage ───────────────────────────────────────────────────────────────────

def read_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        if "session_policies" in raw:
            return _from_hermes(raw)
        # legacy flat format — migrate on next write
        return raw
    except Exception:
        return copy.deepcopy(DEFAULT_CONFIG)


def write_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        yaml.dump(_to_hermes(cfg), default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


# ── Masking ───────────────────────────────────────────────────────────────────

def _mask(cfg: dict[str, Any]) -> dict[str, Any]:
    masked = copy.deepcopy(cfg)
    for pcfg in masked.get("platforms", {}).values():
        for field in ("token", "password"):
            val = pcfg.get(field, "")
            if val:
                pcfg[field] = val[:4] + _MASK if len(val) > 4 else _MASK
    return masked


def _is_masked(value: str) -> bool:
    return bool(value) and _MASK in value


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/config")
def get_config(_: dict = Depends(require_role("admin"))):
    return _mask(read_config())


@router.get("/config/schema")
def get_schema(_: dict = Depends(require_role("admin"))):
    return {
        "providers": PROVIDERS,
        "toolsets": AVAILABLE_TOOLSETS,
        "streaming_modes": STREAMING_MODES,
        "session_modes": SESSION_MODES,
    }


@router.put("/config")
def update_config(body: dict[str, Any], _: dict = Depends(require_role("admin"))):
    current = read_config()

    for key in ("model", "provider", "max_iterations", "enabled_toolsets",
                "session_reset_mode", "session_reset_hour", "streaming_mode"):
        if key in body:
            current[key] = body[key]

    if "platforms" in body:
        for platform, pcfg in body["platforms"].items():
            current["platforms"].setdefault(platform, {})
            for field, value in pcfg.items():
                if field in ("token", "password") and _is_masked(str(value)):
                    continue
                current["platforms"][platform][field] = value

    write_config(current)
    return {"status": "ok"}
