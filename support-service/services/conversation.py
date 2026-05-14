import logging
import re
from datetime import datetime, timezone

from db import get_supabase
from services.freshservice_connector import FreshserviceConnector

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 600  # 10 min de inatividade dispara prompt de retomada

ONBOARDING_STATES = frozenset({
    "onboarding_email",
    "onboarding_confirm_fs",
    "onboarding_ask_location_fs",
    "onboarding_name",
    "onboarding_company",
    "onboarding_location",
    "onboarding_final_confirm",
    "onboarding_empresa",
})

CATALOG: dict[str, dict] = {
    "1": {
        "label": "💻 TI",
        "category": "TI",
        "workspace_id": 2,
        "subcategories": {
            "1": "Hardware",
            "2": "Software",
            "3": "Rede / Internet",
            "4": "Acesso / Senha",
            "5": "E-mail",
            "6": "Outros TI",
        },
    },
    "2": {
        "label": "🧾 Financeiro",
        "category": "Financeiro",
        "workspace_id": 5,
        "subcategories": {
            "1": "Reembolso",
            "2": "Nota Fiscal",
            "3": "Pagamentos",
            "4": "Outros Financeiro",
        },
    },
    "3": {
        "label": "🏢 RH / Pessoal",
        "category": "RH",
        "workspace_id": 6,
        "subcategories": {
            "1": "Admissão",
            "2": "Benefícios",
            "3": "Férias / Afastamento",
            "4": "Documentos",
            "5": "Outros RH",
        },
    },
    "4": {
        "label": "✈️ Operações",
        "category": "Operações",
        "workspace_id": 13,
        "subcategories": {
            "1": "Reservas",
            "2": "Emissão de Bilhetes",
            "3": "Reemissão / Cancelamento",
            "4": "Outros Operações",
        },
    },
    "5": {
        "label": "📦 Suprimentos",
        "category": "Suprimentos",
        "workspace_id": 18,
        "subcategories": {
            "1": "Compras",
            "2": "Estoque",
            "3": "Fornecedores",
            "4": "Outros Suprimentos",
        },
    },
}

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

EMPRESAS = {
    "1": "VTC OPERADORA LOGÍSTICA (Matriz)",
    "2": "VOETUR TURISMO (Matriz)",
    "3": "VIP CARGAS BRASÍLIA (Matriz)",
    "4": "VIP SERVICE CLUB MARINA (Matriz)",
    "5": "VIP CARGAS RIO (MATRIZ)",
}
EMPRESA_MSG = (
    "🏢 Qual é a sua empresa?\n\n"
    + "\n".join(f"{k} - {v}" for k, v in EMPRESAS.items())
)

_FS_COMPANY_TO_EMPRESA_KEY: dict[str, str] = {
    "vtc operadora logística": "1",
    "vtc operadora logistica": "1",
    "voetur turismo": "2",
    "vip cargas brasília": "3",
    "vip cargas brasilia": "3",
    "vip service club marina": "4",
    "vip cargas rio": "5",
}

_TICKET_STATUS_MAP = {
    2: "Aberto 🟡",
    3: "Pendente ⏳",
    4: "Resolvido ✅",
    5: "Fechado 🔒",
}


def _match_empresa_key(company_name: str | None) -> str | None:
    if not company_name:
        return None
    return _FS_COMPANY_TO_EMPRESA_KEY.get(company_name.lower().strip())


def _is_back(text: str) -> bool:
    return text.strip().lower() in {"voltar", "0", "menu", "início", "inicio"}


WELCOME = (
    "👋 Olá! Sou o *VoeIA*, seu assistente de suporte da Voetur.\n\n"
    "Para começar, por favor me informe seu *e-mail corporativo*:"
)
CATALOG_MSG = (
    "📋 *Central de Demandas VoeIA*\n\n"
    "Selecione o departamento:\n\n"
    "1 - 💻 TI\n"
    "2 - 🧾 Financeiro\n"
    "3 - 🏢 RH / Pessoal\n"
    "4 - ✈️ Operações\n"
    "5 - 📦 Suprimentos"
)
RESUME_MSG = (
    "Sua conversa anterior ficou pausada por inatividade. 😴\n\n"
    "Deseja continuar de onde parou?\n"
    "*1* — Sim, continuar\n"
    "*2* — Não, recomeçar do início"
)


class ConversationFSM:
    def __init__(self) -> None:
        self._fs = FreshserviceConnector()

    def process(self, phone: str, text: str, jid: str = "") -> str:
        db = get_supabase()
        text = text.strip()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Load or create conversation
        is_new = False
        conv_res = db.table("support_conversations").select("*").eq("phone", phone).execute()
        if conv_res.data:
            conv = conv_res.data[0]
        else:
            is_new = True
            db.table("support_conversations").insert({
                "phone": phone,
                "state": "onboarding_email",
                "context": {},
                "last_activity": now_iso,
                "session_status": "active",
                "session_jid": jid,
            }).execute()
            conv_res2 = db.table("support_conversations").select("*").eq("phone", phone).execute()
            conv = conv_res2.data[0]

        # Load user profile
        user_res = db.table("support_users").select("*").eq("phone", phone).execute()
        user = user_res.data[0] if user_res.data else None

        # New contact: send welcome
        if is_new:
            self._log_messages(db, conv, text, WELCOME)
            return WELCOME

        state = conv["state"]
        ctx: dict = conv.get("context") or {}

        # Inactivity timeout check — skips onboarding and resume states
        if state not in ONBOARDING_STATES and state != "awaiting_resume":
            last_activity = conv.get("last_activity")
            if last_activity:
                try:
                    last_dt = datetime.fromisoformat(last_activity)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
                    if elapsed > TIMEOUT_SECONDS:
                        resume_ctx = {
                            "_pre_timeout_state": state,
                            "_pre_timeout_context": dict(ctx),
                        }
                        self._save_conv(db, conv, {
                            "state": "awaiting_resume",
                            "context": resume_ctx,
                            "session_status": "timed_out",
                            "session_jid": jid or conv.get("session_jid") or "",
                            "last_activity": now_iso,
                        })
                        self._log_messages(db, conv, text, RESUME_MSG)
                        return RESUME_MSG
                except Exception:
                    pass

        handler = getattr(self, f"_handle_{state}", self._handle_unknown)
        reply, new_state, new_ctx = handler(phone, text, ctx, user, db)

        self._save_conv(db, conv, {
            "state": new_state,
            "context": new_ctx,
            "last_activity": now_iso,
            "session_jid": jid or conv.get("session_jid") or "",
            "session_status": "active",
        })

        self._log_messages(db, conv, text, reply)
        return reply

    # ── state handlers ───────────────────────────────────────────────

    def _handle_onboarding_email(self, phone, text, ctx, user, db):
        if user and user.get("profile_complete"):
            return self._show_main_menu(phone, db)

        if not _EMAIL_RE.fullmatch(text):
            return (
                "Por favor, informe um *e-mail válido* para continuar.\n"
                "Exemplo: seu.nome@voetur.com.br",
                "onboarding_email",
                {},
            )

        requester = self._fs.search_requester_by_email(text)
        if requester:
            name = requester.get("name", "").strip()
            location = requester.get("location_name") or ""
            depts = ", ".join(requester.get("department_names") or []) or "—"
            empresa_key = _match_empresa_key(requester.get("company_name"))
            empresa_name = EMPRESAS.get(empresa_key, "") if empresa_key else ""
            empresa_line = f"*Empresa:* {empresa_name}\n" if empresa_name else ""
            msg = (
                f"✅ Encontrei seu cadastro:\n\n"
                f"*Nome:* {name}\n"
                f"*E-mail:* {requester['primary_email']}\n"
                f"*Filial:* {location or '(não informada)'}\n"
                f"*Departamento(s):* {depts}\n"
                f"{empresa_line}"
                f"\nEsses dados estão corretos?\n"
                f"1 - ✅ Sim\n"
                f"2 - ❌ Não, quero corrigir"
            )
            return msg, "onboarding_confirm_fs", {
                "email": text,
                "fs_requester": requester,
                "empresa_key": empresa_key,
            }
        else:
            return (
                "Não encontrei seu cadastro. Vamos criá-lo agora.\n\nQual é o seu *nome completo*?",
                "onboarding_name",
                {"email": text},
            )

    def _handle_onboarding_confirm_fs(self, phone, text, ctx, user, db):
        requester = ctx.get("fs_requester", {})
        if text == "1":
            location = requester.get("location_name") or ""
            if not location:
                return (
                    "Qual é a sua *filial* (cidade/unidade)?",
                    "onboarding_ask_location_fs",
                    ctx,
                )
            empresa_key = ctx.get("empresa_key")
            upsert_data = {
                "email": requester.get("primary_email", ""),
                "name": requester.get("name", ""),
                "freshservice_requester_id": requester.get("id"),
                "location": location,
            }
            if empresa_key:
                upsert_data["empresa"] = EMPRESAS[empresa_key]
                upsert_data["profile_complete"] = True
                self._upsert_user(db, phone, upsert_data)
                return self._show_main_menu(phone, db)
            else:
                self._upsert_user(db, phone, upsert_data)
                return EMPRESA_MSG, "onboarding_empresa", {}
        else:
            return (
                "Sem problemas! Vamos preencher manualmente.\n\nQual é o seu *nome completo*?",
                "onboarding_name",
                {"email": ctx.get("email", "")},
            )

    def _handle_onboarding_ask_location_fs(self, phone, text, ctx, user, db):
        requester = ctx.get("fs_requester", {})
        empresa_key = ctx.get("empresa_key")
        upsert_data = {
            "email": requester.get("primary_email", ""),
            "name": requester.get("name", ""),
            "freshservice_requester_id": requester.get("id"),
            "location": text.strip(),
        }
        if empresa_key:
            upsert_data["empresa"] = EMPRESAS[empresa_key]
            upsert_data["profile_complete"] = True
            self._upsert_user(db, phone, upsert_data)
            return self._show_main_menu(phone, db)
        else:
            self._upsert_user(db, phone, upsert_data)
            return EMPRESA_MSG, "onboarding_empresa", {}

    def _handle_onboarding_empresa(self, phone, text, ctx, user, db):
        if text not in EMPRESAS:
            return (EMPRESA_MSG + "\n\nDigite o número da sua empresa (1–5).", "onboarding_empresa", ctx)
        empresa = EMPRESAS[text]
        self._upsert_user(db, phone, {"empresa": empresa, "profile_complete": True})
        return self._show_main_menu(phone, db)

    def _handle_onboarding_name(self, phone, text, ctx, user, db):
        if len(text) < 2:
            return ("Por favor, informe seu *nome completo*.", "onboarding_name", ctx)
        return (
            "Qual é o nome da sua *empresa / filial*?",
            "onboarding_company",
            {**ctx, "name": text},
        )

    def _handle_onboarding_company(self, phone, text, ctx, user, db):
        return (
            "Qual é a sua *filial* (cidade/unidade)?",
            "onboarding_location",
            {**ctx, "company": text},
        )

    def _handle_onboarding_location(self, phone, text, ctx, user, db):
        name = ctx.get("name", "")
        company = ctx.get("company", "")
        email = ctx.get("email", "")
        msg = (
            f"Confirme seus dados:\n\n"
            f"*Nome:* {name}\n"
            f"*Empresa:* {company}\n"
            f"*Filial:* {text}\n"
            f"*E-mail:* {email}\n\n"
            f"Está correto?\n"
            f"1 - ✅ Sim\n"
            f"2 - ❌ Não, recomeçar"
        )
        return msg, "onboarding_final_confirm", {**ctx, "location": text}

    def _handle_onboarding_final_confirm(self, phone, text, ctx, user, db):
        if text == "1":
            self._upsert_user(db, phone, {
                "email": ctx.get("email", ""),
                "name": ctx.get("name", ""),
                "company": ctx.get("company", ""),
                "location": ctx.get("location", ""),
            })
            return EMPRESA_MSG, "onboarding_empresa", {}
        return (
            "Sem problemas! Vamos recomeçar.\n\nQual é o seu *nome completo*?",
            "onboarding_name",
            {"email": ctx.get("email", "")},
        )

    def _handle_awaiting_resume(self, phone, text, ctx, user, db):
        if text.strip() == "1":
            prev_state = ctx.get("_pre_timeout_state", "main_menu")
            prev_ctx = ctx.get("_pre_timeout_context", {})
            reply = "✅ Continuando de onde parou! Envie sua próxima mensagem."
            return reply, prev_state, prev_ctx
        else:
            return self._show_main_menu(phone, db)

    def _handle_main_menu(self, phone, text, ctx, user, db):
        if text == "1":
            return CATALOG_MSG, "selecting_catalog", {}
        ticket_id = self._parse_ticket_number(text)
        if ticket_id:
            return self._fetch_ticket_status(ticket_id)
        reply, state, new_ctx = self._show_main_menu(phone, db)
        return reply, state, new_ctx

    def _handle_viewing_ticket_status(self, phone, text, ctx, user, db):
        if text == "1":
            return CATALOG_MSG, "selecting_catalog", {}
        return self._show_main_menu(phone, db)

    def _handle_selecting_catalog(self, phone, text, ctx, user, db):
        if text not in CATALOG:
            return (
                CATALOG_MSG + "\n\nDigite o número do departamento (1–5).",
                "selecting_catalog",
                {},
            )
        dept = CATALOG[text]
        subs = "\n".join(f"{k} - {v}" for k, v in dept["subcategories"].items())
        msg = f"*{dept['label']}* — Selecione a subcategoria:\n\n{subs}\n\n0 - ↩️ Voltar"
        return msg, "selecting_subcategory", {"catalog_key": text, "workspace_id": dept["workspace_id"]}

    def _handle_selecting_subcategory(self, phone, text, ctx, user, db):
        if _is_back(text):
            return CATALOG_MSG, "selecting_catalog", {}
        catalog_key = ctx.get("catalog_key", "")
        dept = CATALOG.get(catalog_key, {})
        subcategories = dept.get("subcategories", {})
        if text not in subcategories:
            subs = "\n".join(f"{k} - {v}" for k, v in subcategories.items())
            return (
                f"Opção inválida. Escolha:\n\n{subs}\n\n0 - ↩️ Voltar",
                "selecting_subcategory",
                ctx,
            )
        subcategory = subcategories[text]
        msg = (
            f"O que você deseja fazer?\n\n"
            f"1 - 📝 Abrir novo chamado\n"
            f"2 - 🔍 Consultar chamados em aberto\n"
            f"0 - ↩️ Voltar"
        )
        return msg, "selecting_action", {**ctx, "subcategory": subcategory}

    def _handle_selecting_action(self, phone, text, ctx, user, db):
        if _is_back(text):
            return CATALOG_MSG, "selecting_catalog", {}
        if text == "1":
            return (
                "Descreva sua solicitação com detalhes:\n\n_(Digite 0 para voltar ao menu)_",
                "collecting_description",
                ctx,
            )
        elif text == "2":
            return self._list_open_tickets(phone, ctx, user, db)
        return (
            "Opção inválida. Digite:\n1 - Abrir novo chamado\n2 - Consultar chamados em aberto\n0 - ↩️ Voltar",
            "selecting_action",
            ctx,
        )

    def _handle_collecting_description(self, phone, text, ctx, user, db):
        if _is_back(text):
            return CATALOG_MSG, "selecting_catalog", {}
        if len(text) < 5:
            return ("Descrição muito curta. Por favor, detalhe melhor sua solicitação.\n\n_(Digite 0 para voltar ao menu)_", "collecting_description", ctx)
        dept = CATALOG.get(ctx.get("catalog_key", ""), {})
        subject = f"[{dept.get('category', 'Suporte')}] {ctx.get('subcategory', 'Solicitação')}"
        msg = (
            f"Confirme a abertura do chamado:\n\n"
            f"*Assunto:* {subject}\n"
            f"*Descrição:* {text[:200]}{'...' if len(text) > 200 else ''}\n\n"
            f"1 - ✅ Confirmar\n"
            f"2 - ❌ Cancelar\n"
            f"0 - ↩️ Voltar ao menu"
        )
        return msg, "confirming_ticket", {**ctx, "description": text, "subject": subject}

    def _handle_confirming_ticket(self, phone, text, ctx, user, db):
        if _is_back(text):
            return CATALOG_MSG, "selecting_catalog", {}
        if text != "1":
            return ("Chamado cancelado. " + CATALOG_MSG, "selecting_catalog", {})

        user_row = db.table("support_users").select("*").eq("phone", phone).execute()
        u = user_row.data[0] if user_row.data else {}
        email = u.get("email", "")
        empresa = u.get("empresa", "")
        requester_id = u.get("freshservice_requester_id")
        workspace_id = ctx.get("workspace_id", 2)
        description = ctx.get("description", "")
        subject = ctx.get("subject", ctx.get("subcategory", "Solicitação"))

        try:
            result = self._fs.create_ticket(
                subject=subject,
                description=description,
                email=email,
                workspace_id=workspace_id,
                empresa=empresa,
                requester_id=requester_id,
            )
            ticket = result.get("ticket", {})
            ticket_id = ticket.get("id")
            if ticket_id:
                db.table("support_tickets").insert({
                    "freshservice_ticket_id": ticket_id,
                    "phone": phone,
                    "status": 2,
                    "subject": subject,
                }).execute()
                reply = (
                    f"✅ Chamado *#{ticket_id}* aberto com sucesso!\n"
                    f"Você receberá atualizações aqui pelo WhatsApp.\n\n"
                    f"Digite qualquer mensagem para voltar ao menu principal."
                )
            else:
                reply = "⚠️ Chamado criado, mas não consegui obter o número. Nossa equipe entrará em contato."
        except Exception as exc:
            logger.error("create_ticket error for %s: %s", phone, exc)
            reply = (
                "❌ Erro ao abrir chamado. Tente novamente ou acesse o portal:\n"
                "https://suporte.voetur.com.br/"
            )

        return reply, "idle", {}

    def _handle_awaiting_ticket_selection(self, phone, text, ctx, user, db):
        return self._show_main_menu(phone, db)

    def _handle_idle(self, phone, text, ctx, user, db):
        return self._show_main_menu(phone, db)

    def _handle_unknown(self, phone, text, ctx, user, db):
        return WELCOME, "onboarding_email", {}

    # ── helpers ──────────────────────────────────────────────────────

    def _show_main_menu(self, phone: str, db) -> tuple[str, str, dict]:
        """Exibe menu inicial: abrir novo chamado + lista de chamados abertos (se houver)."""
        u = db.table("support_users").select("email").eq("phone", phone).execute()
        email = u.data[0].get("email", "") if u.data else ""
        tickets = self._fs.get_all_open_tickets(email) if email else []

        if not tickets:
            return CATALOG_MSG, "selecting_catalog", {}

        lines = ["👋 Como posso ajudar?\n", "*1.* 📝 Abrir novo chamado\n", "📋 *Chamados em aberto:*"]
        for t in tickets[:5]:
            lines.append(f"#*{t.get('id')}* — {t.get('subject', '(sem assunto)')}")
        lines.append("\n_Digite *1* para novo chamado ou o número do chamado para ver o status._")
        return "\n".join(lines), "main_menu", {}

    def _parse_ticket_number(self, text: str) -> int | None:
        t = text.strip().lstrip("#")
        if t.isdigit() and 1 <= len(t) <= 8:
            return int(t)
        return None

    def _fetch_ticket_status(self, ticket_id: int) -> tuple[str, str, dict]:
        ticket = self._fs.get_ticket(ticket_id)
        if not ticket:
            return (
                "❌ Chamado não encontrado.\n\nDigite *1* para novo chamado ou *0* para voltar ao menu.",
                "main_menu",
                {},
            )
        status = _TICKET_STATUS_MAP.get(ticket.get("status", 0), "Desconhecido")
        msg = (
            f"📋 *Chamado #{ticket.get('id')}*\n"
            f"*Assunto:* {ticket.get('subject', '(sem assunto)')}\n"
            f"*Status:* {status}\n\n"
            f"*0* — Voltar ao menu  •  *1* — Abrir novo chamado"
        )
        return msg, "viewing_ticket_status", {"viewed_ticket_id": ticket_id}

    def _list_open_tickets(self, phone, ctx, user, db):
        u = db.table("support_users").select("email").eq("phone", phone).execute()
        email = u.data[0].get("email", "") if u.data else ""
        workspace_id = ctx.get("workspace_id")
        tickets = self._fs.get_tickets_by_requester(email, workspace_id) if email else []
        if not tickets:
            return (
                "Não encontrei chamados em aberto para você neste departamento.\n\n"
                + CATALOG_MSG,
                "selecting_catalog",
                {},
            )
        lines = ["📋 *Chamados em aberto:*\n"]
        for t in tickets[:5]:
            lines.append(f"• #{t.get('id')} — {t.get('subject', '(sem assunto)')}")
        lines.append("\nDigite qualquer mensagem para voltar ao menu.")
        return "\n".join(lines), "idle", {}

    def _upsert_user(self, db, phone: str, data: dict) -> None:
        data["phone"] = phone
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            db.table("support_users").upsert(data, on_conflict="phone").execute()
        except Exception as exc:
            logger.error("upsert_user error for %s: %s", phone, exc)

    def _save_conv(self, db, conv: dict, updates: dict) -> None:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            db.table("support_conversations").update(updates).eq("phone", conv["phone"]).execute()
        except Exception as exc:
            logger.error("save_conv error: %s", exc)

    def _log_messages(self, db, conv: dict, inbound: str, outbound: str) -> None:
        try:
            conv_id = conv.get("id")
            if conv_id:
                db.table("support_messages").insert([
                    {"conversation_id": conv_id, "direction": "inbound", "content": inbound},
                    {"conversation_id": conv_id, "direction": "outbound", "content": outbound},
                ]).execute()
        except Exception as exc:
            logger.error("Failed to log messages: %s", exc)
