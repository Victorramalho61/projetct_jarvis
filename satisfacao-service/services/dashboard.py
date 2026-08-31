"""Agregações para o dashboard da Pesquisa de Satisfação (médias, distribuição, alertas de 30%)."""
from datetime import date

LIMIAR_RUIM_PERCENTUAL = 30.0


def _pct(parte: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((parte / total) * 100, 2)


def build_campanha_dashboard(sb, campanha_id: str) -> dict:
    campanha_resp = sb.table("sat_campanhas").select("*").eq("id", campanha_id).single().execute()
    campanha = campanha_resp.data
    if not campanha:
        return {}

    perguntas_resp = (
        sb.table("sat_campanha_perguntas")
        .select("*, sat_perguntas(id, categoria)")
        .eq("campanha_id", campanha_id)
        .order("ordem")
        .execute()
    )
    campanha_perguntas = perguntas_resp.data or []

    respostas_resp = sb.table("sat_respostas").select("*").eq("campanha_id", campanha_id).execute()
    respostas = respostas_resp.data or []
    total_convidados = len(respostas)
    total_enviados = len([r for r in respostas if r["status"] != "pendente"])
    total_respondidos = len([r for r in respostas if r["status"] == "respondido"])

    cp_ids = [cp["id"] for cp in campanha_perguntas]
    itens: list[dict] = []
    if cp_ids:
        itens_resp = (
            sb.table("sat_respostas_itens")
            .select("*")
            .in_("campanha_pergunta_id", cp_ids)
            .execute()
        )
        itens = itens_resp.data or []

    planos_resp = sb.table("sat_planos_acao").select("*").eq("campanha_id", campanha_id).execute()
    planos = planos_resp.data or []
    planos_por_pergunta: dict[str, list[dict]] = {}
    for p in planos:
        planos_por_pergunta.setdefault(p["pergunta_id"], []).append(p)

    perguntas_out = []
    for cp in campanha_perguntas:
        pergunta_id = (cp.get("sat_perguntas") or {}).get("id")
        itens_pergunta = [i for i in itens if i["campanha_pergunta_id"] == cp["id"]]
        notas = [i["nota"] for i in itens_pergunta]
        total_notas = len(notas)
        distribuicao = {str(n): notas.count(n) for n in range(1, 6)}
        qtd_ruim = distribuicao["1"] + distribuicao["2"]
        pct_ruim = _pct(qtd_ruim, total_notas)
        media = round(sum(notas) / total_notas, 2) if total_notas else None
        pendentes_triagem = len([i for i in itens_pergunta if i["triagem_status"] == "pendente"])

        perguntas_out.append({
            "campanha_pergunta_id": cp["id"],
            "pergunta_id": pergunta_id,
            "ordem": cp["ordem"],
            "texto": cp["texto_snapshot"],
            "total_respostas": total_notas,
            "media": media,
            "distribuicao": distribuicao,
            "percentual_ruim": pct_ruim,
            "alerta_plano_acao": pct_ruim > LIMIAR_RUIM_PERCENTUAL,
            "pendentes_triagem": pendentes_triagem,
            "planos_acao": planos_por_pergunta.get(pergunta_id, []),
        })

    dias_restantes = None
    if campanha.get("data_prazo"):
        prazo = date.fromisoformat(campanha["data_prazo"])
        dias_restantes = (prazo - date.today()).days

    todas_notas = [i["nota"] for i in itens]
    total_avaliacoes = len(todas_notas)
    distribuicao_geral = {str(n): todas_notas.count(n) for n in range(1, 6)}
    qtd_ruim = distribuicao_geral["1"] + distribuicao_geral["2"]
    qtd_bom = distribuicao_geral["4"] + distribuicao_geral["5"]

    return {
        "campanha": campanha,
        "envio": {
            "total_convidados": total_convidados,
            "total_enviados": total_enviados,
            "percentual_enviado": _pct(total_enviados, total_convidados),
        },
        "aderencia": {
            "total_convidados": total_convidados,
            "total_respondidos": total_respondidos,
            "percentual": _pct(total_respondidos, total_convidados),
            "atingiu_minimo": _pct(total_respondidos, total_convidados) >= 30.0,
        },
        "notas_gerais": {
            "total_avaliacoes": total_avaliacoes,
            "media": round(sum(todas_notas) / total_avaliacoes, 2) if total_avaliacoes else None,
            "distribuicao": distribuicao_geral,
            "percentual_ruim": _pct(qtd_ruim, total_avaliacoes),
            "percentual_neutro": _pct(distribuicao_geral["3"], total_avaliacoes),
            "percentual_bom": _pct(qtd_bom, total_avaliacoes),
        },
        "dias_restantes": dias_restantes,
        "perguntas": perguntas_out,
    }


def build_historico() -> list[dict]:
    from db import get_supabase
    sb = get_supabase()

    campanhas_resp = sb.table("sat_campanhas").select("id, ano, titulo, status").order("ano").execute()
    campanhas = campanhas_resp.data or []

    historico = []
    for c in campanhas:
        cp_resp = (
            sb.table("sat_campanha_perguntas")
            .select("id, sat_perguntas(categoria)")
            .eq("campanha_id", c["id"])
            .execute()
        )
        campanha_perguntas = cp_resp.data or []
        cp_ids = [cp["id"] for cp in campanha_perguntas]
        cp_categoria = {cp["id"]: (cp.get("sat_perguntas") or {}).get("categoria") for cp in campanha_perguntas}

        itens: list[dict] = []
        if cp_ids:
            itens_resp = (
                sb.table("sat_respostas_itens")
                .select("nota, campanha_pergunta_id")
                .in_("campanha_pergunta_id", cp_ids)
                .execute()
            )
            itens = itens_resp.data or []

        por_categoria: dict[str, list[int]] = {}
        for i in itens:
            cat = cp_categoria.get(i["campanha_pergunta_id"]) or "outro"
            por_categoria.setdefault(cat, []).append(i["nota"])

        medias_por_categoria = {
            cat: round(sum(notas) / len(notas), 2) for cat, notas in por_categoria.items() if notas
        }
        todas_notas = [n for notas in por_categoria.values() for n in notas]
        media_geral = round(sum(todas_notas) / len(todas_notas), 2) if todas_notas else None

        historico.append({
            "ano": c["ano"],
            "titulo": c["titulo"],
            "status": c["status"],
            "media_geral": media_geral,
            "medias_por_categoria": medias_por_categoria,
        })

    return historico
