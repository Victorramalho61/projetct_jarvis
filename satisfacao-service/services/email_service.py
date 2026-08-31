"""Templates de e-mail para Pesquisa de Satisfação de Clientes — Grupo Voetur."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from db import get_settings

_logger = logging.getLogger(__name__)

_BRAND_GREEN = "#00694E"
_BRAND_DARK  = "#004F3A"
_BRAND_LIGHT = "#E6F4F0"
_TEXT_DARK   = "#1A1A2E"
_BG          = "#F4F6FB"
_WHITE       = "#FFFFFF"
_FOOTER_BG   = "#111827"
_LINK_GREEN  = "#4FC49A"
_ERROR_BG    = "#FEF2F2"
_ERROR_BORDER= "#EF4444"

_LOGO_BRANCO = "https://grupovoetur.com.br/wp-content/uploads/2024/09/Grupo-Logo-Branco.svg"
_SGI_EMAIL_FALLBACK = "sgi@voetur.com.br"

_SOCIALS = [
    ("LinkedIn",  "https://www.linkedin.com/company/grupo-voetur/"),
    ("Instagram", "https://www.instagram.com/grupovoetur/"),
    ("Facebook",  "https://www.facebook.com/GrupoVoetur"),
]


def _footer() -> str:
    socials = " &nbsp;&middot;&nbsp; ".join(
        f'<a href="{u}" style="color:{_LINK_GREEN};text-decoration:none;font-size:11px;">{n}</a>'
        for n, u in _SOCIALS
    )
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="padding-bottom:14px;border-bottom:1px solid #1F2937;">
    <img src="{_LOGO_BRANCO}" alt="Grupo Voetur" height="22"
         style="display:block;height:22px;max-width:160px;margin-bottom:6px;"
         onerror="this.style.display='none'"/>
    <p style="margin:0;color:#6B7280;font-size:11px;font-style:italic;">Movimentamos o melhor do Brasil</p>
  </td></tr>
  <tr><td style="padding-top:16px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="vertical-align:top;padding-right:16px;">
        <p style="margin:0 0 5px;color:#D1D5DB;font-size:11px;font-weight:600;">Pesquisa de Satisfação de Clientes</p>
        <p style="margin:8px 0 0;color:#4B5563;font-size:10px;">E-mail automático — não responda esta mensagem.</p>
      </td>
      <td align="right" style="vertical-align:top;">
        <p style="margin:0 0 8px;color:#D1D5DB;font-size:11px;font-weight:600;">Siga-nos</p>
        <p style="margin:0 0 10px;line-height:1.8;">{socials}</p>
        <p style="margin:0;color:#374151;font-size:10px;">&copy; 2026 Grupo Voetur</p>
      </td>
    </tr></table>
  </td></tr>
</table>"""


def _base(header_html: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
</head>
<body style="margin:0;padding:0;background:{_BG};font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{_BG};padding:24px 12px;">
  <tr><td align="center">
  <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">
    <tr><td style="background:{_BRAND_DARK};height:5px;border-radius:12px 12px 0 0;font-size:0;">&nbsp;</td></tr>
    <tr><td style="background:{_BRAND_GREEN};padding:24px 32px 28px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td><img src="{_LOGO_BRANCO}" alt="Grupo Voetur" height="32"
                 style="display:block;height:32px;max-width:200px;"
                 onerror="this.style.display='none'"/></td>
        <td align="right" style="color:#E6F4F0;font-size:12px;">{header_html}</td>
      </tr></table>
    </td></tr>
    <tr><td style="background:{_WHITE};padding:32px;border-left:1px solid #E5E7EB;border-right:1px solid #E5E7EB;">
      {body_html}
    </td></tr>
    <tr><td style="background:{_FOOTER_BG};padding:24px 32px;border-radius:0 0 12px 12px;">
      {_footer()}
    </td></tr>
  </table>
  </td></tr>
</table>
</body></html>"""


def _cliente_card(cliente: dict, campanha_titulo: str) -> str:
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:{_BRAND_LIGHT};border-radius:8px;padding:16px;margin-bottom:20px;">
  <tr>
    <td style="padding:12px 16px;">
      <p style="margin:0 0 4px;font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:.5px;">Empresa</p>
      <p style="margin:0;font-size:16px;font-weight:700;color:{_TEXT_DARK};">{cliente.get("empresa_nome","—")}</p>
    </td>
  </tr>
  <tr><td style="padding:0 16px 12px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td width="50%" style="vertical-align:top;padding-right:8px;">
        <p style="margin:0 0 2px;font-size:11px;color:#6B7280;">Contato</p>
        <p style="margin:0;font-size:13px;color:{_TEXT_DARK};font-weight:600;">{cliente.get("contato_nome") or "—"}</p>
      </td>
      <td width="50%" style="vertical-align:top;padding-left:8px;">
        <p style="margin:0 0 2px;font-size:11px;color:#6B7280;">Campanha</p>
        <p style="margin:0;font-size:13px;color:{_TEXT_DARK};font-weight:600;">{campanha_titulo}</p>
      </td>
    </tr></table>
  </td></tr>
</table>"""


def _cta_button(link: str, label: str = "Responder Pesquisa") -> str:
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0;">
  <tr><td align="center">
    <a href="{link}"
       style="display:inline-block;background:{_BRAND_GREEN};color:{_WHITE};
              font-size:15px;font-weight:700;text-decoration:none;
              padding:14px 40px;border-radius:8px;letter-spacing:.3px;">
      {label}
    </a>
  </td></tr>
</table>
<p style="text-align:center;font-size:11px;color:#9CA3AF;margin:0 0 8px;">
  Link pessoal e intransferível.
</p>"""


def _send(to_email: str, to_name: str, subject: str, html: str) -> bool:
    s = get_settings()
    if not s.smtp_user:
        _logger.warning("SMTP não configurado — e-mail não enviado para %s", to_email)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"Sistema Jarvis <{s.smtp_from}>"
        msg["To"]      = f"{to_name} <{to_email}>"
        msg["Subject"] = subject
        msg.attach(MIMEText("Visualize este e-mail em um cliente que suporte HTML.", "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as srv:
            srv.starttls()
            srv.ehlo()
            srv.login(s.smtp_user, s.smtp_password)
            srv.sendmail(msg["From"], [to_email], msg.as_string())
        return True
    except Exception as exc:
        _logger.error("Falha ao enviar e-mail para %s: %s", to_email, exc)
        return False


# ─── Templates públicos ───────────────────────────────────────────────────────

def send_primeiro_envio(cliente: dict, campanha: dict, token: str) -> bool:
    s = get_settings()
    contato_nome  = cliente.get("contato_nome") or "Cliente"
    contato_email = cliente.get("contato_email") or ""
    if not contato_email:
        return False

    link = f"{s.frontend_url}/satisfacao/responder/{token}"
    card = _cliente_card(cliente, campanha.get("titulo", ""))
    btn  = _cta_button(link)

    body = f"""
<h2 style="margin:0 0 8px;font-size:20px;color:{_TEXT_DARK};">Pesquisa de Satisfação de Clientes</h2>
<p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.6;">
  Olá, <strong>{contato_nome}</strong>!<br><br>
  Sua opinião é muito importante para nós. Pedimos alguns minutos para responder
  à nossa <strong>Pesquisa de Satisfação de Clientes</strong> e nos ajudar a
  melhorar cada vez mais os nossos serviços.
</p>
{card}
{btn}"""

    html = _base("Pesquisa de Satisfação", body)
    subject = f"[Voetur Viagens] Pesquisa de Satisfação de Clientes — {campanha.get('titulo','')}"
    return _send(contato_email, contato_nome, subject, html)


def send_cobranca(cliente: dict, campanha: dict, resposta: dict) -> bool:
    s = get_settings()
    contato_nome  = cliente.get("contato_nome") or "Cliente"
    contato_email = cliente.get("contato_email") or ""
    token = resposta.get("token") or ""
    if not contato_email or not token:
        return False

    link = f"{s.frontend_url}/satisfacao/responder/{token}"
    total_envios = resposta.get("total_envios", 0)
    card = _cliente_card(cliente, campanha.get("titulo", ""))
    btn  = _cta_button(link, "Responder Agora")

    body = f"""
<div style="background:{_ERROR_BG};border-left:4px solid {_ERROR_BORDER};
            padding:14px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
  <p style="margin:0;font-size:13px;color:#7F1D1D;font-weight:700;">
    ⚠️ Pesquisa pendente de resposta
  </p>
  <p style="margin:4px 0 0;font-size:12px;color:#991B1B;">
    Esta é a {total_envios + 1}ª notificação. Sua participação é muito importante.
  </p>
</div>
<h2 style="margin:0 0 8px;font-size:20px;color:{_TEXT_DARK};">Lembrete: Pesquisa de Satisfação</h2>
<p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.6;">
  Olá, <strong>{contato_nome}</strong>!<br><br>
  Ainda não recebemos sua resposta à Pesquisa de Satisfação de Clientes.
  Pedimos alguns minutos do seu tempo para nos ajudar a melhorar.
</p>
{card}
{btn}"""

    html = _base("⚠️ Lembrete — Pesquisa Pendente", body)
    subject = f"[PENDENTE] Pesquisa de Satisfação de Clientes — {campanha.get('titulo','')}"
    return _send(contato_email, contato_nome, subject, html)


def send_reforco_adesao(cliente: dict, campanha: dict, resposta: dict) -> bool:
    """Reforço enviado pelo Comercial quando a aderência geral está abaixo da meta."""
    s = get_settings()
    contato_nome  = cliente.get("contato_nome") or "Cliente"
    contato_email = cliente.get("contato_email") or ""
    token = resposta.get("token") or ""
    if not contato_email or not token:
        return False

    link = f"{s.frontend_url}/satisfacao/responder/{token}"
    card = _cliente_card(cliente, campanha.get("titulo", ""))
    btn  = _cta_button(link, "Responder Pesquisa")

    body = f"""
<h2 style="margin:0 0 8px;font-size:20px;color:{_TEXT_DARK};">Sua opinião ainda não chegou até nós</h2>
<p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.6;">
  Olá, <strong>{contato_nome}</strong>!<br><br>
  Prorrogamos o prazo da nossa Pesquisa de Satisfação de Clientes para que você
  tenha a oportunidade de compartilhar sua experiência conosco. Sua participação
  nos ajuda a melhorar continuamente.
</p>
{card}
{btn}"""

    html = _base("Prazo Prorrogado — Pesquisa de Satisfação", body)
    subject = f"[Prazo Prorrogado] Pesquisa de Satisfação de Clientes — {campanha.get('titulo','')}"
    return _send(contato_email, contato_nome, subject, html)


def send_confirmacao_sgi(cliente: dict, campanha: dict, itens_ruins: int) -> bool:
    s = get_settings()
    sgi_email = s.sgi_email or _SGI_EMAIL_FALLBACK
    card = _cliente_card(cliente, campanha.get("titulo", ""))
    link_painel = f"{s.frontend_url}/satisfacao/envio"

    alerta = ""
    if itens_ruins > 0:
        alerta = f"""
<div style="background:{_ERROR_BG};border-left:4px solid {_ERROR_BORDER};
            padding:14px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
  <p style="margin:0;font-size:13px;color:#7F1D1D;font-weight:700;">
    ⚠️ {itens_ruins} nota(s) ruim(ns) (1-2) recebida(s) — triagem pendente
  </p>
</div>"""

    body = f"""
<h2 style="margin:0 0 8px;font-size:20px;color:{_TEXT_DARK};">Nova resposta recebida</h2>
<p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.6;">
  O cliente abaixo respondeu à Pesquisa de Satisfação.
</p>
{card}
{alerta}
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:20px 0;">
  <tr><td align="center">
    <a href="{link_painel}"
       style="display:inline-block;background:{_BRAND_GREEN};color:{_WHITE};
              font-size:14px;font-weight:700;text-decoration:none;
              padding:12px 32px;border-radius:8px;">
      Ver no Painel do SGI
    </a>
  </td></tr>
</table>"""

    html = _base("Nova Resposta", body)
    subject = f"[Jarvis] Nova resposta — Pesquisa de Satisfação ({cliente.get('empresa_nome','')})"
    return _send(sgi_email, "SGI Grupo Voetur", subject, html)


def log_email(sb, resposta_id: str, destinatario: str, tipo_email: str, sucesso: bool, erro_detalhe: str | None = None) -> None:
    try:
        sb.table("sat_email_log").insert({
            "resposta_id":  resposta_id,
            "destinatario": destinatario,
            "tipo_email":   tipo_email,
            "sucesso":      sucesso,
            "erro_detalhe": erro_detalhe,
        }).execute()
    except Exception as exc:
        _logger.error("Falha ao registrar log de e-mail: %s", exc)
