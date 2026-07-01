"""Templates de e-mail para Avaliação de Experiência — Grupo Voetur."""
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
_WARN_BG     = "#FFF7ED"
_WARN_BORDER = "#F97316"
_ERROR_BG    = "#FEF2F2"
_ERROR_BORDER= "#EF4444"

_LOGO_BRANCO = "https://grupovoetur.com.br/wp-content/uploads/2024/09/Grupo-Logo-Branco.svg"
_HR_EMAIL    = "rh@voetur.com.br"

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
        <p style="margin:0 0 5px;color:#D1D5DB;font-size:11px;font-weight:600;">Dúvidas? Fale com o RH</p>
        <p style="margin:0;font-size:11px;">
          <a href="mailto:{_HR_EMAIL}" style="color:{_LINK_GREEN};text-decoration:none;">{_HR_EMAIL}</a>
        </p>
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


def _colaborador_card(emp: dict, tipo: str, data_prevista: str) -> str:
    tipo_label = "45 dias" if tipo == "45_dias" else "90 dias"
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:{_BRAND_LIGHT};border-radius:8px;padding:16px;margin-bottom:20px;">
  <tr>
    <td style="padding:12px 16px;">
      <p style="margin:0 0 4px;font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:.5px;">Colaborador</p>
      <p style="margin:0;font-size:16px;font-weight:700;color:{_TEXT_DARK};">{emp.get("nome","—")}</p>
    </td>
  </tr>
  <tr><td style="padding:0 16px 12px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td width="50%" style="vertical-align:top;padding-right:8px;">
        <p style="margin:0 0 2px;font-size:11px;color:#6B7280;">Cargo</p>
        <p style="margin:0;font-size:13px;color:{_TEXT_DARK};font-weight:600;">{emp.get("cargo") or "—"}</p>
      </td>
      <td width="50%" style="vertical-align:top;padding-left:8px;">
        <p style="margin:0 0 2px;font-size:11px;color:#6B7280;">Empresa</p>
        <p style="margin:0;font-size:13px;color:{_TEXT_DARK};font-weight:600;">{emp.get("empresa") or "—"}</p>
      </td>
    </tr><tr>
      <td width="50%" style="vertical-align:top;padding-right:8px;padding-top:10px;">
        <p style="margin:0 0 2px;font-size:11px;color:#6B7280;">Admissão</p>
        <p style="margin:0;font-size:13px;color:{_TEXT_DARK};font-weight:600;">{emp.get("data_admissao") or "—"}</p>
      </td>
      <td width="50%" style="vertical-align:top;padding-left:8px;padding-top:10px;">
        <p style="margin:0 0 2px;font-size:11px;color:#6B7280;">Vencimento ({tipo_label})</p>
        <p style="margin:0;font-size:13px;color:{_BRAND_GREEN};font-weight:700;">{data_prevista}</p>
      </td>
    </tr></table>
  </td></tr>
</table>"""


def _cta_button(link: str, label: str = "Avaliar Agora") -> str:
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
  Link pessoal e intransferível. Válido por 30 dias.
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

def send_primeiro_envio(avaliacao: dict, emp: dict, token: str) -> bool:
    s = get_settings()
    tipo = avaliacao.get("tipo", "45_dias")
    tipo_label = "45 Dias" if tipo == "45_dias" else "90 Dias"
    data_prev = avaliacao.get("data_prevista", "—")
    link = f"{s.frontend_url}/experiencia/avaliar/{token}"

    gestor_nome  = emp.get("gestor_nome") or "Líder"
    gestor_email = emp.get("gestor_email") or ""
    if not gestor_email:
        return False

    card = _colaborador_card(emp, tipo, data_prev)
    btn  = _cta_button(link)

    body = f"""
<h2 style="margin:0 0 8px;font-size:20px;color:{_TEXT_DARK};">Avaliação de Experiência — {tipo_label}</h2>
<p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.6;">
  Olá, <strong>{gestor_nome}</strong>!<br><br>
  É hora de realizar a <strong>Avaliação de Experiência de {tipo_label}</strong>
  do(a) colaborador(a) abaixo. Seu parecer é fundamental para o desenvolvimento
  e a trajetória desta pessoa no Grupo Voetur.
</p>
{card}
<div style="background:{_BRAND_LIGHT};border-left:4px solid {_BRAND_GREEN};
            padding:14px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
  <p style="margin:0;font-size:13px;color:{_TEXT_DARK};">
    <strong>Certifique-se</strong> de que sua avaliação esteja sendo
    <strong>justa e imparcial</strong>. Avalie cada indicador com base no
    desempenho observado no período.
  </p>
</div>
{btn}"""

    html = _base("Avaliação de Experiência", body)
    subject = f"[Jarvis] Avaliação de Experiência {tipo_label} — {emp.get('nome','')}"
    return _send(gestor_email, gestor_nome, subject, html)


def send_cobranca(avaliacao: dict, emp: dict) -> bool:
    s = get_settings()
    tipo = avaliacao.get("tipo", "45_dias")
    tipo_label = "45 Dias" if tipo == "45_dias" else "90 Dias"
    data_prev = avaliacao.get("data_prevista", "—")
    token = avaliacao.get("token") or ""
    link  = f"{s.frontend_url}/experiencia/avaliar/{token}"

    gestor_nome  = emp.get("gestor_nome") or "Líder"
    gestor_email = emp.get("gestor_email") or ""
    if not gestor_email or not token:
        return False

    from datetime import date
    total_envios = avaliacao.get("total_envios", 0)
    card = _colaborador_card(emp, tipo, data_prev)
    btn  = _cta_button(link, "Responder Avaliação")

    body = f"""
<div style="background:{_ERROR_BG};border-left:4px solid {_ERROR_BORDER};
            padding:14px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
  <p style="margin:0;font-size:13px;color:#7F1D1D;font-weight:700;">
    ⚠️ Avaliação pendente de resposta
  </p>
  <p style="margin:4px 0 0;font-size:12px;color:#991B1B;">
    Esta é a {total_envios + 1}ª notificação. Por favor, realize a avaliação o quanto antes.
  </p>
</div>
<h2 style="margin:0 0 8px;font-size:20px;color:{_TEXT_DARK};">Lembrete: Avaliação de Experiência — {tipo_label}</h2>
<p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.6;">
  Olá, <strong>{gestor_nome}</strong>!<br><br>
  A avaliação de experiência do(a) colaborador(a) abaixo ainda <strong>não foi concluída</strong>.
  O prazo já venceu ou está próximo. Sua ação é necessária.
</p>
{card}
{btn}"""

    html = _base("⚠️ Cobrança — Avaliação Pendente", body)
    subject = f"[PENDENTE] Avaliação de Experiência {tipo_label} — {emp.get('nome','')}"
    return _send(gestor_email, gestor_nome, subject, html)


def send_confirmacao_rh(avaliacao: dict, emp: dict, parecer: str, assinado_em: str) -> bool:
    s = get_settings()
    rh_email = _HR_EMAIL
    tipo = avaliacao.get("tipo", "45_dias")
    tipo_label = "45 Dias" if tipo == "45_dias" else "90 Dias"
    data_prev = avaliacao.get("data_prevista", "—")

    gestor_nome = emp.get("gestor_nome") or "—"
    colab_nome  = emp.get("nome") or "—"
    empresa     = emp.get("empresa") or "—"

    # Cor do parecer
    parecer_label_map = {
        "seguir":      ("Seguir contrato por mais 45 dias", _BRAND_GREEN),
        "interromper": ("Interromper o contrato nos 45 dias", "#EF4444"),
        "efetivar":    ("Efetivação do colaborador", _BRAND_GREEN),
        "encerrar":    ("Encerrar contrato nos 90 dias", "#EF4444"),
    }
    parecer_label, parecer_color = parecer_label_map.get(parecer, (parecer, "#6B7280"))
    card = _colaborador_card(emp, tipo, data_prev)

    link_painel = f"{s.frontend_url}/experiencia?tab=auditoria"

    body = f"""
<h2 style="margin:0 0 8px;font-size:20px;color:{_TEXT_DARK};">
  Avaliação Concluída — {tipo_label}
</h2>
<p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.6;">
  O líder <strong>{gestor_nome}</strong> concluiu a avaliação de experiência
  do(a) colaborador(a) abaixo.
</p>
{card}
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;
              padding:16px;margin-bottom:20px;">
  <tr><td style="padding:12px 16px;">
    <p style="margin:0 0 6px;font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:.5px;">Parecer do Líder</p>
    <p style="margin:0;font-size:16px;font-weight:700;color:{parecer_color};">
      {parecer_label}
    </p>
  </td></tr>
  <tr><td style="padding:0 16px 12px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td width="50%" style="padding-right:8px;">
        <p style="margin:0 0 2px;font-size:11px;color:#6B7280;">Assinado digitalmente em</p>
        <p style="margin:0;font-size:13px;color:{_TEXT_DARK};font-weight:600;">{assinado_em}</p>
      </td>
      <td width="50%" style="padding-left:8px;">
        <p style="margin:0 0 2px;font-size:11px;color:#6B7280;">Empresa</p>
        <p style="margin:0;font-size:13px;color:{_TEXT_DARK};font-weight:600;">{empresa}</p>
      </td>
    </tr></table>
  </td></tr>
</table>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:20px 0;">
  <tr><td align="center">
    <a href="{link_painel}"
       style="display:inline-block;background:{_BRAND_GREEN};color:{_WHITE};
              font-size:14px;font-weight:700;text-decoration:none;
              padding:12px 32px;border-radius:8px;">
      Ver no Painel de Auditoria
    </a>
  </td></tr>
</table>"""

    html = _base("Avaliação Concluída", body)
    subject = f"[Jarvis] Avaliação {tipo_label} concluída — {colab_nome}"
    return _send(rh_email, "RH Grupo Voetur", subject, html)


def log_email(sb, avaliacao_id: str, destinatario: str, tipo_email: str, sucesso: bool) -> None:
    try:
        sb.table("exp_email_log").insert({
            "avaliacao_id": avaliacao_id,
            "destinatario": destinatario,
            "tipo_email":   tipo_email,
            "sucesso":      sucesso,
        }).execute()
    except Exception as exc:
        _logger.error("Falha ao registrar log de e-mail: %s", exc)
