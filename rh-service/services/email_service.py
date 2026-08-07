"""E-mail do relatório semanal de vagas — RH/Grupo Voetur."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from db import get_settings

log = logging.getLogger(__name__)

_BRAND_GREEN = "#00694E"
_BRAND_DARK = "#004F3A"
_TEXT_DARK = "#1A1A2E"
_BG = "#F4F6FB"
_WHITE = "#FFFFFF"
_ERROR_BG = "#FEF2F2"
_ERROR_BORDER = "#EF4444"
_WARN_BG = "#FFF7ED"
_WARN_BORDER = "#F97316"
_LOGO_BRANCO = "https://grupovoetur.com.br/wp-content/uploads/2024/09/Grupo-Logo-Branco.svg"


def _base(header_html: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/></head>
<body style="margin:0;padding:0;background:{_BG};font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{_BG};padding:24px 12px;">
  <tr><td align="center">
  <table width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;">
    <tr><td style="background:{_BRAND_DARK};height:5px;border-radius:12px 12px 0 0;font-size:0;">&nbsp;</td></tr>
    <tr><td style="background:{_BRAND_GREEN};padding:24px 32px 28px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td><img src="{_LOGO_BRANCO}" alt="Grupo Voetur" height="32" style="display:block;height:32px;max-width:200px;" onerror="this.style.display='none'"/></td>
        <td align="right" style="color:#E6F4F0;font-size:12px;">{header_html}</td>
      </tr></table>
    </td></tr>
    <tr><td style="background:{_WHITE};padding:32px;border-left:1px solid #E5E7EB;border-right:1px solid #E5E7EB;">
      {body_html}
    </td></tr>
    <tr><td style="background:#111827;padding:16px 32px;border-radius:0 0 12px 12px;">
      <p style="margin:0;color:#6B7280;font-size:11px;">Jarvis — Módulo de Recursos Humanos. E-mail automático, não responda.</p>
    </td></tr>
  </table>
  </td></tr>
</table>
</body></html>"""


def _tabela_vagas(titulo: str, cor_borda: str, cor_bg: str, vagas: list[dict]) -> str:
    if not vagas:
        return f"""
<div style="background:#F0FDF4;border-left:4px solid {_BRAND_GREEN};padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
  <p style="margin:0;font-size:13px;color:{_TEXT_DARK};"><strong>{titulo}:</strong> nenhuma vaga.</p>
</div>"""
    linhas = "".join(
        f"""<tr style="border-bottom:1px solid #E5E7EB;">
              <td style="padding:6px 8px;font-size:12px;">{v.get('numero_requisicao') or '—'}</td>
              <td style="padding:6px 8px;font-size:12px;">{v.get('cargo') or '—'}</td>
              <td style="padding:6px 8px;font-size:12px;">{v.get('responsavel') or '—'}</td>
              <td style="padding:6px 8px;font-size:12px;text-align:center;">{v.get('dias_corridos')}/{v.get('sla_alvo_dias')}</td>
              <td style="padding:6px 8px;font-size:12px;">{v.get('etapa_atual') or '—'}</td>
            </tr>"""
        for v in vagas
    )
    return f"""
<div style="background:{cor_bg};border-left:4px solid {cor_borda};padding:12px 16px 4px;border-radius:0 8px 8px 0;margin-bottom:20px;">
  <p style="margin:0 0 8px;font-size:13px;color:{_TEXT_DARK};font-weight:700;">{titulo} ({len(vagas)})</p>
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{_WHITE};border-radius:6px;">
    <tr style="background:#F9FAFB;">
      <td style="padding:6px 8px;font-size:11px;color:#6B7280;font-weight:700;">Nº Requisição</td>
      <td style="padding:6px 8px;font-size:11px;color:#6B7280;font-weight:700;">Cargo</td>
      <td style="padding:6px 8px;font-size:11px;color:#6B7280;font-weight:700;">Analista</td>
      <td style="padding:6px 8px;font-size:11px;color:#6B7280;font-weight:700;text-align:center;">Dias/SLA</td>
      <td style="padding:6px 8px;font-size:11px;color:#6B7280;font-weight:700;">Etapa</td>
    </tr>
    {linhas}
  </table>
</div>"""


def send_relatorio_semanal(destinatario: str, nome: str, kpis: dict, sla_estourado: list[dict], sla_estourando: list[dict]) -> bool:
    s = get_settings()
    if not s.smtp_user:
        log.warning("SMTP não configurado — relatório semanal não enviado para %s", destinatario)
        return False

    resumo = f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:20px;">
  <tr>
    <td width="25%" style="text-align:center;padding:8px;"><p style="margin:0;font-size:22px;font-weight:700;color:{_BRAND_GREEN};">{kpis.get('abertas', 0)}</p><p style="margin:0;font-size:11px;color:#6B7280;">Abertas</p></td>
    <td width="25%" style="text-align:center;padding:8px;"><p style="margin:0;font-size:22px;font-weight:700;color:{_TEXT_DARK};">{kpis.get('concluidas_periodo', 0)}</p><p style="margin:0;font-size:11px;color:#6B7280;">Concluídas</p></td>
    <td width="25%" style="text-align:center;padding:8px;"><p style="margin:0;font-size:22px;font-weight:700;color:{_ERROR_BORDER};">{len(sla_estourado)}</p><p style="margin:0;font-size:11px;color:#6B7280;">SLA estourado</p></td>
    <td width="25%" style="text-align:center;padding:8px;"><p style="margin:0;font-size:22px;font-weight:700;color:{_WARN_BORDER};">{len(sla_estourando)}</p><p style="margin:0;font-size:11px;color:#6B7280;">SLA estourando</p></td>
  </tr>
</table>"""

    body = f"""
<h2 style="margin:0 0 8px;font-size:20px;color:{_TEXT_DARK};">Status Semanal das Vagas — Recursos Humanos</h2>
<p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.6;">Olá, <strong>{nome}</strong>! Segue o resumo semanal de todas as vagas em andamento.</p>
{resumo}
{_tabela_vagas("SLA estourado", _ERROR_BORDER, _ERROR_BG, sla_estourado)}
{_tabela_vagas("SLA estourando (≤3 dias)", _WARN_BORDER, _WARN_BG, sla_estourando)}
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:20px 0;">
  <tr><td align="center">
    <a href="{s.frontend_url}/rh" style="display:inline-block;background:{_BRAND_GREEN};color:{_WHITE};font-size:14px;font-weight:700;text-decoration:none;padding:12px 32px;border-radius:8px;">Ver Dashboard Completo</a>
  </td></tr>
</table>"""

    html = _base("Relatório Semanal", body)
    subject = f"[Jarvis] Status semanal de vagas — {sla_estourado and 'SLA estourado' or 'RH'}"

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = s.smtp_from or "Sistema Jarvis <noreply@voetur.com.br>"
        msg["To"] = f"{nome} <{destinatario}>"
        msg["Subject"] = subject
        msg.attach(MIMEText("Visualize este e-mail em um cliente que suporte HTML.", "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as srv:
            srv.starttls()
            srv.ehlo()
            srv.login(s.smtp_user, s.smtp_password)
            srv.sendmail(msg["From"], [destinatario], msg.as_string())
        return True
    except Exception as exc:
        log.error("Falha ao enviar relatório semanal para %s: %s", destinatario, exc)
        return False
