"""
Classificação LLM de artigos PayFly.
Primário: Google Gemini 2.0 Flash (grátis).
Fallback: Groq llama-3.1-8b-instant (grátis).
Usa httpx diretamente — sem dependência de langchain.
"""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

_CATEGORIES = {"Reclamação", "Elogio", "Imprensa", "Crise", "Jurídico", "Neutro"}
_SENTIMENTS = {"muito_negativo", "negativo", "neutro", "positivo", "muito_positivo"}

_PROMPT = """\
Você é um analista de mídia especializado em viagens corporativas brasileiras.
Analise os títulos abaixo sobre a empresa PayFly (plataforma de gestão de viagens corporativas).
Responda SOMENTE com um JSON array, sem texto extra, sem markdown.

Títulos:
{headlines}

Formato exigido:
[{{"idx": 0, "category": "Imprensa", "sentiment_label": "positivo"}}, ...]

Categorias válidas: Reclamação, Elogio, Imprensa, Crise, Jurídico, Neutro
Sentimentos válidos: muito_negativo, negativo, neutro, positivo, muito_positivo
"""


_BATCH = 30   # artigos por chamada LLM


async def classify_articles_llm(
    articles: list[dict],
    google_api_key: str = "",
    groq_api_key: str = "",
) -> list[dict]:
    if not articles or (not google_api_key and not groq_api_key):
        return articles

    # Processa em batches para não exceder tokens de saída
    for batch_start in range(0, len(articles), _BATCH):
        batch = articles[batch_start:batch_start + _BATCH]
        headlines = "\n".join(
            f'[{i}] "{a.get("title", "")}"'
            for i, a in enumerate(batch)
        )
        prompt = _PROMPT.format(headlines=headlines)

        raw: str | None = None
        if google_api_key:
            raw = await _gemini(prompt, google_api_key)
        if not raw and groq_api_key:
            raw = await _groq(prompt, groq_api_key)

        if not raw:
            logger.warning("media_classifier: LLM falhou no batch %d", batch_start)
            continue

        # Extrai JSON mesmo que venha com markdown ou texto extra
        try:
            start = raw.index("[")
            end   = raw.rindex("]") + 1
            classifications = json.loads(raw[start:end])
        except Exception as exc:
            logger.warning("media_classifier parse error: %s | raw: %.300s", exc, raw)
            continue

        for item in classifications:
            idx = item.get("idx")
            if idx is None or not isinstance(idx, int) or idx >= len(batch):
                continue
            global_idx = batch_start + idx
            cat  = item.get("category", "Neutro")
            sent = item.get("sentiment_label", "neutro")
            if cat in _CATEGORIES:
                articles[global_idx]["category"] = cat
            if sent in _SENTIMENTS:
                articles[global_idx]["sentiment_label"] = sent
                if "negativo" in sent:
                    articles[global_idx]["sentiment"] = "negativo"
                elif "positivo" in sent:
                    articles[global_idx]["sentiment"] = "positivo"
                else:
                    articles[global_idx]["sentiment"] = "neutro"

        logger.info("media_classifier: batch %d/%d classificado", batch_start + len(batch), len(articles))

    return articles


async def _gemini(prompt: str, api_key: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
                },
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        logger.warning("media_classifier[gemini]: %s", exc)
        return None


async def _groq(prompt: str, api_key: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("media_classifier[groq]: %s", exc)
        return None
