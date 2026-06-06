#!/usr/bin/env python3
"""
Cria permissões de teste no módulo de cartões.

Uso:
  cd cards-service
  pip install -r requirements.txt
  python scripts/seed_test_users.py

O script busca usuários pelo e-mail na tabela de usuários do core-service
(via Supabase) e insere nas cards_permissoes.

Edite as variáveis EMAIL_COLABORADOR e EMAIL_SUPERVISOR antes de rodar.
"""

import os
import sys

EMAIL_COLABORADOR = "colaborador@voetur.com.br"  # ← altere para e-mail real
EMAIL_SUPERVISOR  = "supervisor@voetur.com.br"    # ← altere para e-mail real

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def find_user(email: str) -> dict | None:
    res = sb.table("users").select("id, username, display_name, email").eq("email", email).maybe_single().execute()
    return res.data


def upsert_permission(user: dict, perfil: str):
    sb.table("cards_permissoes").upsert(
        {
            "user_id": user["id"],
            "user_login": user.get("email") or user.get("username"),
            "user_nome": user.get("display_name") or user.get("username"),
            "perfil": perfil,
            "ativo": True,
        },
        on_conflict="user_id",
    ).execute()
    print(f"  ✓ {perfil:12} → {user['display_name']} ({user['email']})")


def main():
    print("Cards Service — Seed de permissões de teste\n")

    for email, perfil in [(EMAIL_COLABORADOR, "colaborador"), (EMAIL_SUPERVISOR, "supervisor")]:
        print(f"Buscando usuário: {email}")
        user = find_user(email)
        if not user:
            print(f"  ✗ Usuário não encontrado: {email}")
            print(f"    → Crie o usuário no Jarvis primeiro e atualize o e-mail no script.")
            continue
        upsert_permission(user, perfil)

    print("\nPermissões gravadas em cards_permissoes.")
    print("Acesse /cartoes para testar cada perfil.")


if __name__ == "__main__":
    main()
