import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from db import get_settings

_logger = logging.getLogger(__name__)


def send_email(to_email: str, display_name: str, subject: str, html: str) -> bool:
    s = get_settings()
    if not s.smtp_user:
        _logger.debug("SMTP not configured — skipping email to %s", to_email)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = s.smtp_from or s.smtp_user
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html", "utf-8"))

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
    company_name: str, branch_name: str,
    cycle_name: str, token: str, frontend_url: str,
) -> bool:
    subject = f"Formulário de Avaliação — {cycle_name} | {company_name}"
    link = f"{frontend_url}/avaliar/{token}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
    <h2 style="color:#1F4E79">Avaliação de Desempenho — {cycle_name}</h2>
    <p>Olá, <strong>{evaluator_name}</strong>!</p>
    <p>Você tem colaboradores para avaliar no ciclo <strong>{cycle_name}</strong> — {company_name} / {branch_name}.</p>
    <p><strong>⚠️ Este link é pessoal e intransferível.</strong> Não compartilhe com terceiros.</p>
    <p style="margin:24px 0">
      <a href="{link}" style="background:#1F4E79;color:white;padding:12px 24px;text-decoration:none;border-radius:4px;font-size:16px">
        Acessar Formulário de Avaliação
      </a>
    </p>
    <p style="color:#888;font-size:12px">Caso o botão não funcione, copie: {link}</p>
    </div>
    """
    return send_email(evaluator_email, evaluator_name, subject, html)


def send_ciencia_email(
    employee_name: str, employee_email: str,
    evaluator_name: str, cycle_name: str,
    token: str, frontend_url: str,
) -> bool:
    subject = f"Resultado da Sua Avaliação — {cycle_name}"
    link = f"{frontend_url}/ciencia/{token}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
    <h2 style="color:#1F4E79">Resultado da Avaliação de Desempenho</h2>
    <p>Olá, <strong>{employee_name}</strong>!</p>
    <p>Sua avaliação de desempenho do ciclo <strong>{cycle_name}</strong> foi concluída pelo(a)
       gestor(a) <strong>{evaluator_name}</strong>.</p>
    <p>Clique abaixo para visualizar suas notas e confirmar que está ciente do resultado:</p>
    <p style="margin:24px 0">
      <a href="{link}" style="background:#166534;color:white;padding:12px 24px;text-decoration:none;border-radius:4px;font-size:16px">
        Ver Avaliação e Dar Ciência
      </a>
    </p>
    <p style="color:#888;font-size:12px">Este link expira em 30 dias. Caso não funcione: {link}</p>
    </div>
    """
    return send_email(employee_email, employee_name, subject, html)
