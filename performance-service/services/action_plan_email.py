"""E-mails do Plano de Ação - Feedback.

Reaproveita branding e infraestrutura de envio de services/email.py — nenhuma
linha desse arquivo é alterada, só importada.
"""
from services.email import (
    _BRAND_GREEN, _BRAND_LIGHT, _TEXT_DARK, _TEXT_MUTED, _WHITE,
    _email_base, send_email,
)

def _items_list_html(items: list[dict], show_plan_text: bool = False, show_progress: bool = False) -> str:
    rows = []
    for it in items:
        extra = ""
        if show_plan_text and it.get("plan_text"):
            extra += (
                f'<p style="margin:4px 0 0;color:{_TEXT_MUTED};font-size:12px;line-height:1.5;">'
                f'{it["plan_text"]}</p>'
            )
        if show_progress:
            extra += (
                f'<p style="margin:4px 0 0;color:{_TEXT_MUTED};font-size:12px;">'
                f'Progresso acumulado até aqui: <strong>{it.get("cumulative_pct_before", 0)}%</strong></p>'
            )
        rows.append(f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #E5E7EB;">
            <p style="margin:0;font-size:13px;font-weight:600;color:{_TEXT_DARK};">
              &#8226; {it["indicator_name"]}
            </p>
            {extra}
          </td>
        </tr>""")
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:{_BRAND_LIGHT};border-radius:8px;margin:0 0 24px;overflow:hidden;">
      {''.join(rows)}
    </table>"""


def send_action_plan_initial_email(
    manager_name: str, manager_email: str,
    employee_name: str, cycle_name: str,
    items: list[dict], token: str, frontend_url: str,
    company_name: str = "",
) -> bool:
    subject = f"Plano de Ação de Feedback — {employee_name} ({cycle_name})"
    link = f"{frontend_url}/plano-acao/{token}"

    header_html = f"""
    <p style="margin:18px 0 0;color:rgba(255,255,255,0.85);
              font-size:13px;font-weight:600;letter-spacing:0.3px;">
      &#128203; Plano de Ação de Feedback &mdash; {cycle_name}
    </p>"""

    body_html = f"""
    <p style="margin:0 0 24px;color:{_TEXT_DARK};font-size:16px;font-weight:600;line-height:1.4;">
      Olá, <span style="color:{_BRAND_GREEN};">{manager_name}</span>!
    </p>
    <p style="margin:0 0 20px;color:{_TEXT_MUTED};font-size:14px;line-height:1.7;">
      Na avaliação de desempenho do ciclo <strong style="color:{_TEXT_DARK};">{cycle_name}</strong>,
      <strong style="color:{_TEXT_DARK};">{employee_name}</strong> recebeu nota 1 ou 2 nas
      competências abaixo. Para dar continuidade ao processo de desenvolvimento, pedimos que
      monte um plano de ação com objetivos e metas de melhoria para cada uma delas.
    </p>

    {_items_list_html(items)}

    <table cellpadding="0" cellspacing="0" border="0" style="margin:0 auto 28px;">
      <tr>
        <td align="center" style="border-radius:8px;background:{_BRAND_GREEN};">
          <a href="{link}"
             style="display:inline-block;padding:15px 44px;color:{_WHITE};
                    font-size:16px;font-weight:bold;text-decoration:none;
                    border-radius:8px;letter-spacing:0.3px;">
            &#9998; Preencher Plano de Ação
          </a>
        </td>
      </tr>
    </table>

    <p style="margin:0;color:{_TEXT_MUTED};font-size:12px;text-align:center;line-height:1.6;">
      Caso o botão não funcione, copie e cole:<br/>
      <a href="{link}" style="color:{_BRAND_GREEN};font-size:11px;word-break:break-all;">{link}</a>
    </p>"""

    return send_email(manager_email, manager_name, subject, _email_base(header_html, body_html))


def _checkin_email_html(
    manager_name: str, employee_name: str, cycle_name: str,
    phase_number: int, is_final_phase: bool,
    items: list[dict], token: str, frontend_url: str,
) -> str:
    link = f"{frontend_url}/plano-acao/checkin/{token}"

    header_html = f"""
    <p style="margin:18px 0 0;color:rgba(255,255,255,0.85);
              font-size:13px;font-weight:600;letter-spacing:0.3px;">
      &#128200; Acompanhamento do Plano de Ação &mdash; Fase {phase_number}/4
    </p>"""

    final_notice = ""
    if is_final_phase:
        final_notice = f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:#FEF3C7;border-left:5px solid #D97706;
                  border-radius:0 10px 10px 0;margin:0 0 24px;">
      <tr>
        <td style="padding:14px 18px;">
          <p style="margin:0;font-size:13px;color:{_TEXT_DARK};line-height:1.6;">
            Esta é a <strong>última fase</strong> do acompanhamento (12 meses). Se o percentual
            acumulado de alguma competência não tiver chegado a 100%, o formulário vai pedir para
            você confirmar se o colaborador alcançou a meta mesmo assim, ou justificar o que faltou.
          </p>
        </td>
      </tr>
    </table>"""

    body_html = f"""
    <p style="margin:0 0 24px;color:{_TEXT_DARK};font-size:16px;font-weight:600;line-height:1.4;">
      Olá, <span style="color:{_BRAND_GREEN};">{manager_name}</span>!
    </p>
    <p style="margin:0 0 20px;color:{_TEXT_MUTED};font-size:14px;line-height:1.7;">
      Chegou o checkpoint trimestral do plano de ação de
      <strong style="color:{_TEXT_DARK};">{employee_name}</strong> (ciclo
      <strong style="color:{_TEXT_DARK};">{cycle_name}</strong>). Para cada competência abaixo,
      informe como está o andamento da melhoria.
    </p>

    {_items_list_html(items, show_plan_text=True, show_progress=True)}
    {final_notice}

    <table cellpadding="0" cellspacing="0" border="0" style="margin:0 auto 28px;">
      <tr>
        <td align="center" style="border-radius:8px;background:{_BRAND_GREEN};">
          <a href="{link}"
             style="display:inline-block;padding:15px 44px;color:{_WHITE};
                    font-size:16px;font-weight:bold;text-decoration:none;
                    border-radius:8px;letter-spacing:0.3px;">
            &#9998; Preencher Acompanhamento
          </a>
        </td>
      </tr>
    </table>

    <p style="margin:0;color:{_TEXT_MUTED};font-size:12px;text-align:center;line-height:1.6;">
      Caso o botão não funcione, copie e cole:<br/>
      <a href="{link}" style="color:{_BRAND_GREEN};font-size:11px;word-break:break-all;">{link}</a>
    </p>"""

    return _email_base(header_html, body_html)


def send_action_plan_checkin_email(
    manager_name: str, manager_email: str,
    employee_name: str, cycle_name: str,
    phase_number: int, is_final_phase: bool,
    items: list[dict], token: str, frontend_url: str,
    company_name: str = "",
) -> bool:
    subject = f"Acompanhamento Trimestral (Fase {phase_number}/4) — {employee_name} ({cycle_name})"
    html = _checkin_email_html(
        manager_name, employee_name, cycle_name, phase_number, is_final_phase, items, token, frontend_url,
    )
    return send_email(manager_email, manager_name, subject, html)


def send_action_plan_checkin_reminder_email(
    manager_name: str, manager_email: str,
    employee_name: str, cycle_name: str,
    phase_number: int, is_final_phase: bool,
    items: list[dict], token: str, frontend_url: str,
    company_name: str = "",
) -> bool:
    subject = f"Lembrete: Acompanhamento Trimestral (Fase {phase_number}/4) — {employee_name} ({cycle_name})"
    html = _checkin_email_html(
        manager_name, employee_name, cycle_name, phase_number, is_final_phase, items, token, frontend_url,
    )
    return send_email(manager_email, manager_name, subject, html)
