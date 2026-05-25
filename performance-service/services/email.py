import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from db import get_settings

_logger = logging.getLogger(__name__)

# ── Brand ─────────────────────────────────────────────────────────────────────
_VOETUR_BLUE = "#003D73"
_VTC_TEAL    = "#005F6B"
_ACCENT      = "#F0A500"
_TEXT_DARK   = "#1A1A2E"
_TEXT_MUTED  = "#6B7280"
_BG          = "#F4F6FB"
_WHITE       = "#FFFFFF"
_FOOTER_BG   = "#111827"
_LINK_BLUE   = "#60A5FA"

_LOGO_VOETUR = "https://voeturviagens.com.br/wp-content/uploads/2025/07/voetur-viagens-logo-site.png"
_LOGO_VTC    = "https://www.vtclog.com.br/wp-content/uploads/logo-vtclog.png"

_HR_EMAIL = "rh@voetur.com.br"

_SOCIALS = [
    ("LinkedIn",  "https://www.linkedin.com/company/grupo-voetur/"),
    ("Instagram", "https://www.instagram.com/grupovoetur/"),
    ("Facebook",  "https://www.facebook.com/GrupoVoetur"),
    ("YouTube",   "https://www.youtube.com/@GrupoVoetur-br"),
]


def _footer_html() -> str:
    social_items = " &nbsp;&middot;&nbsp; ".join(
        f'<a href="{url}" style="color:{_LINK_BLUE};text-decoration:none;font-size:11px;">{name}</a>'
        for name, url in _SOCIALS
    )
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding-bottom:14px;border-bottom:1px solid #1F2937;">
      <p style="margin:0 0 2px;color:{_WHITE};font-size:13px;font-weight:bold;letter-spacing:1px;">
        GRUPO VOETUR
      </p>
      <p style="margin:0;color:#6B7280;font-size:11px;font-style:italic;">
        Movimentamos o melhor do Brasil
      </p>
    </td>
  </tr>
  <tr>
    <td style="padding-top:16px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="vertical-align:top;padding-right:16px;">
            <p style="margin:0 0 5px;color:#D1D5DB;font-size:11px;font-weight:600;">
              Dúvidas? Fale com o RH
            </p>
            <p style="margin:0;font-size:11px;line-height:1.6;">
              <a href="mailto:{_HR_EMAIL}"
                 style="color:{_LINK_BLUE};text-decoration:none;">{_HR_EMAIL}</a>
            </p>
            <p style="margin:8px 0 0;color:#4B5563;font-size:10px;line-height:1.6;">
              Voetur Viagens &nbsp;&middot;&nbsp; VTC Operadora Log&iacute;stica<br/>
              E-mail autom&aacute;tico &mdash; n&atilde;o responda a esta mensagem.
            </p>
          </td>
          <td align="right" style="vertical-align:top;">
            <p style="margin:0 0 8px;color:#D1D5DB;font-size:11px;font-weight:600;">Siga-nos</p>
            <p style="margin:0 0 10px;line-height:1.8;">{social_items}</p>
            <p style="margin:0;color:#374151;font-size:10px;">&copy; 2025 Grupo Voetur</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


def _email_base(header_html: str, body_html: str, is_vtclog: bool = False) -> str:
    primary       = _VTC_TEAL    if is_vtclog else _VOETUR_BLUE
    logo_url      = _LOGO_VTC    if is_vtclog else _LOGO_VOETUR
    company_label = "VTC Operadora Logística" if is_vtclog else "Voetur Viagens"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <meta http-equiv="X-UA-Compatible" content="IE=edge"/>
  <title>Sistema Jarvis &mdash; Grupo Voetur</title>
</head>
<body style="margin:0;padding:0;background:{_BG};font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:{_BG};padding:24px 12px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" border="0"
           style="max-width:600px;width:100%;">

      <!-- Barra dourada superior -->
      <tr>
        <td style="background:{_ACCENT};height:5px;
                   border-radius:12px 12px 0 0;font-size:0;">&nbsp;</td>
      </tr>

      <!-- Header com logo -->
      <tr>
        <td style="background:{primary};padding:24px 32px 28px;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="vertical-align:middle;">
                <img src="{logo_url}" alt="{company_label}" height="38"
                     style="display:block;height:38px;max-width:210px;object-fit:contain;"
                     onerror="this.style.display='none'"/>
              </td>
              <td align="right" style="vertical-align:middle;">
                <span style="background:rgba(255,255,255,0.15);color:{_WHITE};
                             font-size:9px;font-weight:bold;padding:5px 13px;
                             border-radius:20px;letter-spacing:1.5px;">
                  SISTEMA JARVIS
                </span>
              </td>
            </tr>
          </table>
          {header_html}
        </td>
      </tr>

      <!-- Corpo -->
      <tr>
        <td style="background:{_WHITE};padding:36px 32px;
                   border-left:1px solid #E5E7EB;border-right:1px solid #E5E7EB;">
          {body_html}
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:{_FOOTER_BG};border-radius:0 0 12px 12px;
                   padding:28px 32px;">
          {_footer_html()}
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def send_email(to_email: str, display_name: str, subject: str, html: str) -> bool:
    s = get_settings()
    if not s.smtp_user:
        _logger.debug("SMTP not configured — skipping email to %s", to_email)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Sistema Jarvis <{s.smtp_from or s.smtp_user}>"
        msg["To"]      = to_email

        # Parte texto simples — obrigatória para evitar "e-mail vazio" em
        # alguns clientes (Outlook / Office 365 mostra partes extras quando
        # MIMEMultipart("alternative") não inclui text/plain).
        plain = (
            "Você recebeu uma notificação do Sistema Jarvis — Grupo Voetur.\n"
            "Por favor, visualize este e-mail em um cliente que suporte HTML.\n\n"
            f"Dúvidas: {_HR_EMAIL}"
        )
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html,  "html",  "utf-8"))

        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(s.smtp_user, s.smtp_password)
            server.sendmail(msg["From"], [to_email], msg.as_string())
        _logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as exc:
        _logger.error("Failed to send email to %s: %s", to_email, exc)
        return False


def send_evaluation_token_email(
    evaluator_name: str, evaluator_email: str,
    employee_name: str, employee_cargo: str,
    company_name: str, branch_name: str,
    cycle_name: str, token: str, frontend_url: str,
) -> bool:
    is_vtclog = (
        "vtc"       in company_name.lower() or
        "logística" in company_name.lower() or
        "logistica" in company_name.lower()
    )
    primary  = _VTC_TEAL if is_vtclog else _VOETUR_BLUE
    light_bg = "#DCEEFB" if not is_vtclog else "#D1EEF2"

    subject = f"Avaliação de Desempenho — {employee_name} | {cycle_name}"
    link    = f"{frontend_url}/avaliar/{token}"

    header_html = f"""
    <p style="margin:18px 0 0;color:rgba(255,255,255,0.85);
              font-size:13px;font-weight:600;letter-spacing:0.3px;">
      &#128202; Gestão de Desempenho &mdash; {cycle_name}
    </p>"""

    body_html = f"""
    <p style="margin:0 0 24px;color:{_TEXT_DARK};font-size:16px;font-weight:600;line-height:1.4;">
      Olá, <span style="color:{primary};">{evaluator_name}</span>!
    </p>
    <p style="margin:0 0 24px;color:{_TEXT_MUTED};font-size:14px;line-height:1.7;">
      Você tem uma avaliação de desempenho pendente no ciclo
      <strong style="color:{_TEXT_DARK};">{cycle_name}</strong>.
      Por favor, acesse o formulário e avalie o colaborador abaixo:
    </p>

    <!-- Card do colaborador -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:{light_bg};border-left:5px solid {primary};
                  border-radius:0 10px 10px 0;margin:0 0 24px;">
      <tr>
        <td style="padding:18px 22px;">
          <p style="margin:0 0 4px;font-size:19px;font-weight:bold;color:{primary};">
            {employee_name}
          </p>
          <p style="margin:0;color:{_TEXT_MUTED};font-size:13px;">
            {employee_cargo} &nbsp;&middot;&nbsp; {company_name} / {branch_name}
          </p>
        </td>
      </tr>
    </table>

    <!-- Aviso -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:#FFFBEB;border:1px solid #FCD34D;
                  border-radius:8px;margin:0 0 28px;">
      <tr>
        <td style="padding:12px 18px;">
          <p style="margin:0;font-size:13px;color:#92400E;line-height:1.6;">
            &#9888;&#65039; <strong>Link individual e intransferível.</strong>
            Este formulário é exclusivo para a avaliação de
            <strong>{employee_name}</strong>. Não compartilhe este link.
          </p>
        </td>
      </tr>
    </table>

    <!-- Botão CTA -->
    <table cellpadding="0" cellspacing="0" border="0"
           style="margin:0 auto 28px;">
      <tr>
        <td align="center"
            style="border-radius:8px;background:{primary};">
          <a href="{link}"
             style="display:inline-block;padding:15px 44px;color:{_WHITE};
                    font-size:16px;font-weight:bold;text-decoration:none;
                    border-radius:8px;letter-spacing:0.5px;">
            Avaliar {employee_name} &rarr;
          </a>
        </td>
      </tr>
    </table>

    <p style="margin:0 0 4px;color:{_TEXT_MUTED};font-size:12px;text-align:center;">
      Caso o botão não funcione, copie e cole o link abaixo:
    </p>
    <p style="margin:0;text-align:center;">
      <a href="{link}"
         style="color:{primary};font-size:11px;word-break:break-all;">{link}</a>
    </p>"""

    return send_email(evaluator_email, evaluator_name, subject,
                      _email_base(header_html, body_html, is_vtclog))


def send_ciencia_email(
    employee_name: str, employee_email: str,
    evaluator_name: str, cycle_name: str,
    token: str, frontend_url: str,
    company_name: str = "",
) -> bool:
    is_vtclog = (
        "vtc"       in company_name.lower() or
        "logística" in company_name.lower() or
        "logistica" in company_name.lower()
    )
    primary  = _VTC_TEAL if is_vtclog else _VOETUR_BLUE
    light_bg = "#DCEEFB" if not is_vtclog else "#D1EEF2"

    subject = f"Resultado da Sua Avaliação de Desempenho — {cycle_name}"
    link    = f"{frontend_url}/ciencia/{token}"

    header_html = f"""
    <p style="margin:18px 0 0;color:rgba(255,255,255,0.85);
              font-size:13px;font-weight:600;letter-spacing:0.3px;">
      &#128203; Resultado da Avaliação &mdash; {cycle_name}
    </p>"""

    body_html = f"""
    <p style="margin:0 0 24px;color:{_TEXT_DARK};font-size:16px;font-weight:600;line-height:1.4;">
      Olá, <span style="color:{primary};">{employee_name}</span>!
    </p>
    <p style="margin:0 0 20px;color:{_TEXT_MUTED};font-size:14px;line-height:1.7;">
      Sua avaliação de desempenho do ciclo
      <strong style="color:{_TEXT_DARK};">{cycle_name}</strong>
      foi concluída pelo(a) gestor(a)
      <strong style="color:{_TEXT_DARK};">{evaluator_name}</strong>.
    </p>

    <!-- Info box -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:{light_bg};border-left:5px solid {primary};
                  border-radius:0 10px 10px 0;margin:0 0 28px;">
      <tr>
        <td style="padding:16px 20px;">
          <p style="margin:0;font-size:14px;color:{_TEXT_DARK};line-height:1.7;">
            Acesse o link abaixo para visualizar suas notas detalhadas e
            <strong>confirmar que está ciente do resultado</strong>.
          </p>
        </td>
      </tr>
    </table>

    <!-- Botão CTA -->
    <table cellpadding="0" cellspacing="0" border="0"
           style="margin:0 auto 28px;">
      <tr>
        <td align="center"
            style="border-radius:8px;background:#166534;">
          <a href="{link}"
             style="display:inline-block;padding:15px 44px;color:{_WHITE};
                    font-size:16px;font-weight:bold;text-decoration:none;
                    border-radius:8px;letter-spacing:0.3px;">
            &#10003; Ver Resultado e Dar Ciência
          </a>
        </td>
      </tr>
    </table>

    <!-- Aviso expiração -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:#F9FAFB;border:1px solid #E5E7EB;
                  border-radius:8px;margin:0 0 16px;">
      <tr>
        <td style="padding:12px 18px;">
          <p style="margin:0;font-size:12px;color:{_TEXT_MUTED};line-height:1.6;">
            &#128336; Este link expira em <strong>30 dias</strong>.
            Após esse prazo, procure o RH para dar sua ciência
            presencialmente.
          </p>
        </td>
      </tr>
    </table>

    <p style="margin:0;color:{_TEXT_MUTED};font-size:12px;text-align:center;
              line-height:1.6;">
      Caso o botão não funcione, copie e cole:<br/>
      <a href="{link}"
         style="color:{primary};font-size:11px;word-break:break-all;">{link}</a>
    </p>"""

    return send_email(employee_email, employee_name, subject,
                      _email_base(header_html, body_html, is_vtclog))
