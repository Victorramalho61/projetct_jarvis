import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

const API = import.meta.env.VITE_API_URL ?? "";
const HR_EMAIL = "rh@voetur.com.br";

const ESCALA_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: "Não atende",        color: "border-red-500    bg-red-50    text-red-700    dark:bg-red-900/30    dark:text-red-300"    },
  2: { label: "Atende Parcialmente",color: "border-amber-500  bg-amber-50  text-amber-700  dark:bg-amber-900/30  dark:text-amber-300"  },
  3: { label: "Atende",             color: "border-blue-500   bg-blue-50   text-blue-700   dark:bg-blue-900/30   dark:text-blue-300"   },
  4: { label: "Supera",             color: "border-emerald-500 bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" },
};

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
      <p className="text-xs text-gray-400">
        Dúvidas?{" "}
        <a href={`mailto:${HR_EMAIL}`} className="text-[#00694E] hover:underline">{HR_EMAIL}</a>
      </p>
      <p className="text-xs text-gray-400 mt-1">© 2026 Grupo Voetur</p>
    </footer>
  );
}

export default function PublicExperienciaPage() {
  const { token } = useParams<{ token: string }>();
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [data, setData]         = useState<any>(null);
  const [indicadores, setIndicadores] = useState<Record<string, number>>({});
  const [textos, setTextos]     = useState<Record<string, string>>({});
  const [parecer, setParecer]   = useState<string>("");
  const [concordou, setConcordou] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sucesso, setSucesso]   = useState(false);

  useEffect(() => {
    fetch(`${API}/api/experiencia/formulario/${token}`)
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
    if (!concordou) { alert("É necessário concordar com a declaração para assinar."); return; }
    if (!parecer) { alert("Selecione o parecer final."); return; }

    const missing = (data?.formulario?.indicadores || []).filter((i: any) => !indicadores[i.id]);
    if (missing.length) { alert(`Avalie todos os indicadores. Faltam: ${missing.map((i: any) => i.label).join(", ")}`); return; }

    const respostas = {
      indicadores,
      pontos_destaque:  textos.pontos_destaque  || "",
      pontos_melhoria:  textos.pontos_melhoria  || "",
      acoes_planejadas: textos.acoes_planejadas || "",
      parecer,
    };

    setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/experiencia/formulario/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          respostas,
          gestor_concordou: true,
          timestamp_assinatura: new Date().toISOString(),
        }),
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
          <p className="text-xs text-gray-400 mt-4">Em caso de dúvidas, contate: <a href={`mailto:${HR_EMAIL}`} className="text-[#00694E] hover:underline">{HR_EMAIL}</a></p>
        </div>
      </div>
    );
  }

  if (sucesso) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="text-5xl mb-4">✅</div>
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-2">Avaliação registrada!</h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            Sua avaliação e assinatura digital foram registradas com sucesso.
            O RH foi notificado.
          </p>
        </div>
      </div>
    );
  }

  const f = data?.formulario || {};
  const emp = data?.colaborador || {};
  const tipo = data?.tipo || "45_dias";
  const tipoLabel = tipo === "45_dias" ? "45 Dias" : "90 Dias";

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-[#00694E] px-6 py-5">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <Logo />
          <span className="text-white/80 text-sm font-medium">Avaliação de Experiência — {tipoLabel}</span>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Aviso */}
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6 text-sm text-amber-800">
          <strong>Certifique-se</strong> de que sua avaliação esteja sendo <strong>justa e imparcial</strong>.
        </div>

        {/* Card do colaborador */}
        <div className="bg-[#E6F4F0] rounded-xl p-5 mb-6 border border-[#00694E]/20">
          <p className="text-xs text-[#00694E] font-semibold uppercase tracking-wider mb-1">Colaborador em avaliação</p>
          <p className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-3">{emp.nome || "—"}</p>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><p className="text-xs text-gray-500">Cargo</p><p className="font-semibold text-gray-800">{emp.cargo || "—"}</p></div>
            <div><p className="text-xs text-gray-500">Empresa</p><p className="font-semibold text-gray-800">{emp.empresa || "—"}</p></div>
            <div><p className="text-xs text-gray-500">Admissão</p><p className="font-semibold text-gray-800">{emp.data_admissao || "—"}</p></div>
            <div><p className="text-xs text-gray-500">Setor</p><p className="font-semibold text-gray-800">{emp.departamento || "—"}</p></div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Indicadores */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
            <h3 className="font-bold text-gray-900 dark:text-gray-100 mb-1">Avaliação dos Indicadores</h3>
            <p className="text-xs text-gray-500 mb-5">Selecione uma opção para cada indicador.</p>

            <div className="space-y-6">
              {(f.indicadores || []).map((ind: any) => (
                <div key={ind.id}>
                  <p className="font-semibold text-gray-800 dark:text-gray-200 mb-2">{ind.label}</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {[1, 2, 3, 4].map((val) => {
                      const opt = ESCALA_LABELS[val];
                      const selected = indicadores[ind.id] === val;
                      return (
                        <button
                          key={val}
                          type="button"
                          onClick={() => setIndicadores((prev) => ({ ...prev, [ind.id]: val }))}
                          className={`border-2 rounded-lg p-2 text-center text-xs font-semibold transition-all ${
                            selected
                              ? opt.color + " ring-2 ring-offset-1 ring-current"
                              : "border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-400"
                          }`}
                        >
                          <span className="block text-sm font-bold">{val}</span>
                          <span className="block leading-tight">{opt.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Campos de texto */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm space-y-5">
            <h3 className="font-bold text-gray-900 dark:text-gray-100">Observações</h3>
            {(f.campos_texto || []).map((campo: any) => (
              <div key={campo.id}>
                <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">{campo.label}</label>
                <textarea
                  value={textos[campo.id] || ""}
                  onChange={(e) => setTextos((prev) => ({ ...prev, [campo.id]: e.target.value }))}
                  rows={3}
                  placeholder={`Descreva ${campo.label.toLowerCase()}...`}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm resize-y
                             bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                             focus:outline-none focus:ring-2 focus:ring-[#00694E]/40 focus:border-[#00694E]"
                />
              </div>
            ))}
          </div>

          {/* Parecer */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
            <h3 className="font-bold text-gray-900 dark:text-gray-100 mb-4">Parecer do Líder</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(f.parecer || []).map((opt: any) => {
                const isGreen = opt.id === "seguir" || opt.id === "efetivar";
                const selected = parecer === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setParecer(opt.id)}
                    className={`border-2 rounded-xl p-4 text-sm font-semibold text-left transition-all ${
                      selected
                        ? isGreen
                          ? "border-[#00694E] bg-[#E6F4F0] text-[#00694E]"
                          : "border-red-500 bg-red-50 text-red-700"
                        : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-400"
                    }`}
                  >
                    <span className="block text-lg mb-1">{isGreen ? "✅" : "⛔"}</span>
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Assinatura digital */}
          <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-600 p-6">
            <h3 className="font-bold text-gray-900 dark:text-gray-100 mb-3">Assinatura Digital</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
              <strong>Líder Avaliador:</strong> {data?.gestor_nome || "—"}
            </p>
            <p className="text-xs text-gray-400 mb-4">
              Ao marcar a caixa abaixo, você assina digitalmente esta avaliação.
              Data e hora serão registradas automaticamente.
            </p>
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={concordou}
                onChange={(e) => setConcordou(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-[#00694E] focus:ring-[#00694E]"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300 italic leading-relaxed">
                {f.declaracao_assinatura || "Declaro que as informações preenchidas são verdadeiras e assumo a responsabilidade pelo parecer emitido nesta avaliação de experiência."}
              </span>
            </label>
            {concordou && (
              <p className="text-xs text-[#00694E] mt-3 font-medium">
                ✅ Assinado digitalmente em: {new Date().toLocaleString("pt-BR")}
              </p>
            )}
          </div>

          {/* Botão submit */}
          <button
            type="submit"
            disabled={submitting || !concordou || !parecer}
            className="w-full bg-[#00694E] hover:bg-[#004F3A] disabled:bg-gray-400 disabled:cursor-not-allowed
                       text-white font-bold py-4 rounded-xl text-base transition-colors shadow-sm"
          >
            {submitting ? "Enviando..." : "Confirmar Avaliação e Assinar"}
          </button>
        </form>

        <Footer />
      </div>
    </div>
  );
}
