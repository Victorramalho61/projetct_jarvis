import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

const API = import.meta.env.VITE_API_URL ?? "";

function Logo() {
  return (
    <img src="https://grupovoetur.com.br/wp-content/uploads/2024/09/Grupo-Logo-Branco.svg"
      alt="Grupo Voetur" className="h-8 max-w-[200px] object-contain"
      onError={(e) => { e.currentTarget.style.display = "none"; }} />
  );
}

function Footer() {
  return (
    <footer className="mt-8 border-t border-gray-200 dark:border-gray-700 pt-8 pb-10 text-center">
      <img src="https://grupovoetur.com.br/wp-content/uploads/2024/09/Grupo-Logo-Verde.svg"
        alt="Grupo Voetur" className="h-7 mx-auto mb-2 object-contain"
        onError={(e) => { e.currentTarget.style.display = "none"; }} />
      <p className="text-xs text-gray-400 italic mb-4">Movimentamos o melhor do Brasil</p>
      <p className="text-xs text-gray-400 mt-1">© 2026 Grupo Voetur</p>
    </footer>
  );
}

type Pergunta = { campanha_pergunta_id: string; ordem: number; texto: string };

type Formulario = {
  resposta_id: string;
  campanha_titulo: string;
  cliente: { empresa_nome: string; contato_nome: string };
  perguntas: Pergunta[];
};

export default function PublicSatisfacaoPage() {
  const { token } = useParams<{ token: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<Formulario | null>(null);
  const [notas, setNotas] = useState<Record<string, number>>({});
  const [comentarios, setComentarios] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [sucesso, setSucesso] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/satisfacao/formulario/${token}`)
      .then((r) => {
        if (!r.ok) return r.json().then((e) => { throw new Error(e.detail || "Erro ao carregar"); });
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const faltando = (data?.perguntas || []).filter((p) => !notas[p.campanha_pergunta_id]);
    if (faltando.length) { alert("Responda todas as perguntas antes de enviar."); return; }

    const itens = (data?.perguntas || []).map((p) => ({
      campanha_pergunta_id: p.campanha_pergunta_id,
      nota: notas[p.campanha_pergunta_id],
      comentario: comentarios[p.campanha_pergunta_id] || undefined,
    }));

    setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/satisfacao/formulario/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ itens }),
      });
      if (!r.ok) {
        const err = await r.json();
        throw new Error(err.detail || "Erro ao enviar");
      }
      setSucesso(true);
    } catch (e: any) {
      alert(`Erro: ${e.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-[#00694E] border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-2">Link indisponível</h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (sucesso) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="text-5xl mb-4">✅</div>
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-2">Obrigado por responder!</h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm">Sua opinião é muito importante para nós.</p>
        </div>
      </div>
    );
  }

  const cliente = data?.cliente || { empresa_nome: "—", contato_nome: "—" };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="bg-[#00694E] px-6 py-5">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <Logo />
          <span className="text-white/80 text-sm font-medium">Pesquisa de Satisfação de Clientes</span>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="bg-[#E6F4F0] rounded-xl p-5 mb-6 border border-[#00694E]/20">
          <p className="text-xs text-[#00694E] font-semibold uppercase tracking-wider mb-1">Olá</p>
          <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{cliente.contato_nome}</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">{cliente.empresa_nome}</p>
        </div>

        <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
          Considere: 5 - Muito Satisfeito · 4 - Satisfeito · 3 - Satisfação Intermediária/Atende ao Esperado ·
          2 - Insatisfeito · 1 - Muito Insatisfeito.
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          {(data?.perguntas || []).map((p) => (
            <div key={p.campanha_pergunta_id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
              <p className="font-semibold text-gray-800 dark:text-gray-200 mb-3">{p.texto}</p>
              <div className="grid grid-cols-5 gap-2 mb-3">
                {[1, 2, 3, 4, 5].map((n) => {
                  const selected = notas[p.campanha_pergunta_id] === n;
                  return (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setNotas((prev) => ({ ...prev, [p.campanha_pergunta_id]: n }))}
                      className={`border-2 rounded-lg py-3 text-center font-bold transition-all ${
                        selected
                          ? "border-[#00694E] bg-[#E6F4F0] text-[#00694E]"
                          : "border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-400"
                      }`}
                    >
                      {n}
                    </button>
                  );
                })}
              </div>
              <textarea
                value={comentarios[p.campanha_pergunta_id] || ""}
                onChange={(e) => setComentarios((prev) => ({ ...prev, [p.campanha_pergunta_id]: e.target.value }))}
                rows={2}
                placeholder="Comente se julgar oportuno (opcional)"
                className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm resize-y
                           bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                           focus:outline-none focus:ring-2 focus:ring-[#00694E]/40 focus:border-[#00694E]"
              />
            </div>
          ))}

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-[#00694E] hover:bg-[#004F3A] disabled:bg-gray-400 disabled:cursor-not-allowed
                       text-white font-bold py-4 rounded-xl text-base transition-colors shadow-sm"
          >
            {submitting ? "Enviando..." : "Enviar Respostas"}
          </button>
        </form>

        <Footer />
      </div>
    </div>
  );
}
