"""
Seed: registra os 6 microsserviços internos do Jarvis como sistemas monitorados.

Uso: python seed_internal_services.py
Requer: variáveis SUPABASE_URL e SUPABASE_KEY no ambiente (ou .env)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_supabase

_INTERNAL_SERVICES = [
    {
        "name": "core-service",
        "description": "Auth, usuários, admin — porta 8001",
        "url": "http://core-service:8001/ready",
        "system_type": "http",
        "config": {"expected_status": 200, "timeout_seconds": 5},
        "check_interval_minutes": 5,
        "enabled": True,
    },
    {
        "name": "monitoring-service",
        "description": "Monitoramento e health checks — porta 8002",
        "url": "http://monitoring-service:8002/ready",
        "system_type": "http",
        "config": {"expected_status": 200, "timeout_seconds": 5},
        "check_interval_minutes": 5,
        "enabled": True,
    },
    {
        "name": "freshservice-service",
        "description": "Helpdesk Freshservice — porta 8003",
        "url": "http://freshservice-service:8003/ready",
        "system_type": "http",
        "config": {"expected_status": 200, "timeout_seconds": 5},
        "check_interval_minutes": 5,
        "enabled": True,
    },
    {
        "name": "moneypenny-service",
        "description": "Microsoft 365 / Moneypenny — porta 8004",
        "url": "http://moneypenny-service:8004/ready",
        "system_type": "http",
        "config": {"expected_status": 200, "timeout_seconds": 5},
        "check_interval_minutes": 5,
        "enabled": True,
    },
    {
        "name": "agents-service",
        "description": "Agentes IA e pipelines — porta 8005",
        "url": "http://agents-service:8005/ready",
        "system_type": "http",
        "config": {"expected_status": 200, "timeout_seconds": 5},
        "check_interval_minutes": 5,
        "enabled": True,
    },
    {
        "name": "expenses-service",
        "description": "Gastos TI e governança de contratos — porta 8006",
        "url": "http://expenses-service:8006/ready",
        "system_type": "http",
        "config": {"expected_status": 200, "timeout_seconds": 5},
        "check_interval_minutes": 5,
        "enabled": True,
    },
]


def seed():
    db = get_supabase()
    existing = {s["name"] for s in db.table("monitored_systems").select("name").execute().data or []}

    inserted = 0
    for svc in _INTERNAL_SERVICES:
        if svc["name"] in existing:
            print(f"[skip] {svc['name']} já existe")
            continue
        db.table("monitored_systems").insert({
            **svc,
            "consecutive_down_count": 0,
        }).execute()
        print(f"[ok]   {svc['name']} registrado")
        inserted += 1

    print(f"\n{inserted} serviço(s) inserido(s), {len(existing)} já existia(m).")


if __name__ == "__main__":
    seed()
