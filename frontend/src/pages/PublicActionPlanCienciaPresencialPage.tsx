import { useState } from "react";

const SOCIALS = [
  { label: "LinkedIn",  href: "https://www.linkedin.com/company/grupo-voetur/" },
  { label: "Instagram", href: "https://www.instagram.com/grupovoetur/" },
  { label: "Facebook",  href: "https://www.facebook.com/GrupoVoetur" },
  { label: "YouTube",   href: "https://www.youtube.com/@GrupoVoetur-br" },
];

const HR_EMAIL = "rh@voetur.com.br";

function applyCpfMask(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`;
  if (digits.length <= 9) return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
  return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
}

function GrupoVoeturFooter() {
  return (
    <footer className="mt-6 border-t border-gray-200 dark:border-gray-800 pt-8 pb-10 text-center">
      <p className="text-sm font-bold tracking-widest text-gray-700 dark:text-gray-300 uppercase mb-0.5">
        Grupo Voetur
      </p>
      <p className="text-xs text-gray-400 italic mb-5">Movimentamos o melhor do Brasil</p>
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 mb-4">
        {SOCIALS.map((s, i) => (
          <span key={s.label} className="flex items-center gap-x-4">
            <a href={s.href} target="_blank" rel="noopener noreferrer"
              className="text-xs text-gray-500 hover:text-[#00694E] transition-colors">
              {s.label}
            </a>
            {i < SOCIALS.length - 1 && (
              <span className="text-gray-300 dark:text-gray-700 text-xs select-none">·</span>
            )}
          </span>
        ))}
      </div>
      <p className="text-xs text-gray-400 mb-1">
        Dúvidas?{" "}
        <a href={`mailto:${HR_EMAIL}`} className="text-[#00694E] hover:underline">
          {HR_EMAIL}
        </a>
      </p>
      <p className="text-xs text-gray-300 dark:text-gray-600 mt-1">Sistema Jarvis &copy; 2026 — Grupo Voetur</p>
    </footer>
  );
}

type Step = "busca" | "resultado" | "confirmado";

export default function PublicActionPlanCienciaPresencialPage() {
  const [step, setStep] = useState<Step>("busca");
  const [nome, setNome] = useState("");
  const [cpf, setCpf] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [data, setData] = useState<any>(null);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  function validateForm(): string | null {
    const cpfDigits = cpf.replace(/\D/g, "");
    if (cpfDigits.length !== 11) return "CPF inválido. Informe os 11 dígitos.";
    const words = nome.trim().split(/\s+/).filter(Boolean);
    if (words.length < 2) return "Informe o nome completo (mínimo 2 palavras).";
    return null;
  }

  async function handleBuscar(e: React.FormEvent) {
    e.preventDefault();
    const err = validateForm();
    if (err) { setSearchError(err); return; }
    setSearchError("");
    setSearching(true);
    try {
      const res = await fetch("/api/performance/public/action-plans/ciencia-presencial/buscar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome: nome.trim(), cpf: cpf.replace(/\D/g, "") }),
      });
      const json = await res.json();
      if (!res.ok) { setSearchError(json.detail || "Colaborador não encontrado."); setSearching(false); return; }
      setData(json);
      setStep(json.already_acknowledged ? "confirmado" : "resultado");
    } catch {
      setSearchError("Erro de conexão. Tente novamente.");
    } finally {
      setSearching(false);
    }
  }

  async function handleConfirmar() {
    setSubmitting(true);
    setSubmitError("");
    try {
      const res = await fetch("/api/performance/public/action-plans/ciencia-presencial/confirmar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cpf: cpf.replace(/\D/g, ""), action_plan_id: data.action_plan_id }),
      });
      const json = await res.json();
      if (!res.ok) { setSubmitError(json.detail || "Erro."); setSubmitting(false); return; }
      setShowModal(false);
      setStep("confirmado");
    } catch {
      setSubmitError("Erro de conexão."); setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950">
      <header className="bg-[#00694E] shadow-lg">
        <div className="h-1 bg-[#004F3A]" />
        <div className="max-w-2xl mx-auto px-5 py-4">
          <div className="text-white font-semibold text-sm">Sistema Jarvis</div>
          <div className="text-white/60 text-xs">Ciência do Plano de Ação — Presencial</div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">
        {step === "busca" && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 sm:p-8 shadow border">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-1">Consultar Plano de Ação</h2>
            <p className="text-sm text-gray-500 mb-5">
              Informe seu nome completo e CPF para consultar e confirmar ciência do seu plano de ação.
            </p>
            <form onSubmit={handleBuscar} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Nome completo</label>
                <input type="text" value={nome} onChange={e => setNome(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-3 py-2.5 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">CPF</label>
                <input type="text" value={cpf} onChange={e => setCpf(applyCpfMask(e.target.value))}
                  placeholder="000.000.000-00"
                  className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-3 py-2.5 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]" />
              </div>
              {searchError && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3">
                  <p className="text-sm text-red-700 dark:text-red-300">{searchError}</p>
                </div>
              )}
              <button type="submit" disabled={searching}
                className="w-full py-3.5 bg-[#00694E] hover:bg-[#004F3A] text-white font-bold rounded-xl transition-all disabled:opacity-60">
                {searching ? "Buscando..." : "Consultar"}
              </button>
            </form>
          </div>
        )}

        {step === "resultado" && data && (
          <div className="space-y-5">
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 sm:p-8 shadow border">
              <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-1">
                Plano de Ação — {data.employee_name}
              </h2>
              <p className="text-sm text-gray-500 mb-5">Ciclo {data.cycle_name} · Gestor(a): {data.manager_name}</p>
              <div className="space-y-4">
                {(data.items || []).map((it: any, i: number) => (
                  <div key={i} className="border border-gray-100 dark:border-gray-700 rounded-lg p-4">
                    <p className="font-semibold text-sm text-gray-900 dark:text-white mb-2">{it.indicator_name}</p>
                    {[
                      ["Situação observada", it.situacao_observada],
                      ["Meta esperada / Objetivo", it.meta_esperada],
                      ["Ações", it.acoes],
                      ["Responsável pelo acompanhamento", it.responsavel_acompanhamento],
                      ["Como será verificado", it.como_sera_verificado],
                    ].map(([label, value]) => value && (
                      <p key={label as string} className="text-xs text-gray-500 mt-1">
                        <strong className="text-gray-700 dark:text-gray-300">{label}:</strong> {value as string}
                      </p>
                    ))}
                  </div>
                ))}
                {data.frequencia_alinhamento && (
                  <div className="border border-gray-100 dark:border-gray-700 rounded-lg p-4">
                    <p className="font-semibold text-sm text-gray-900 dark:text-white mb-1">Combinados de acompanhamento</p>
                    <p className="text-xs text-gray-500">{data.frequencia_alinhamento}</p>
                  </div>
                )}
              </div>
            </div>
            <button onClick={() => setShowModal(true)}
              className="w-full py-3.5 bg-[#00694E] hover:bg-[#004F3A] text-white font-bold rounded-xl transition-all">
              Confirmar Ciência
            </button>
          </div>
        )}

        {step === "confirmado" && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-10 text-center shadow border">
            <div className="text-5xl mb-4">✅</div>
            <h2 className="text-xl font-bold mb-2">Ciência Confirmada</h2>
            <p className="text-gray-600 dark:text-gray-400">
              {data?.acknowledged_at
                ? `Registrada em ${new Date(data.acknowledged_at).toLocaleString("pt-BR")}.`
                : "Sua ciência já estava registrada."}
            </p>
          </div>
        )}
      </main>

      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-7 max-w-md w-full shadow-2xl">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Confirmação de Ciência</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-5 leading-relaxed">
              Declaro que tomei ciência do meu plano de ação, das competências prioritárias e dos
              combinados de acompanhamento.
            </p>
            {submitError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3 mb-4">
                <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
              </div>
            )}
            <div className="flex flex-col gap-3">
              <button onClick={handleConfirmar} disabled={submitting}
                className="w-full py-3.5 bg-green-600 hover:bg-green-700 text-white font-bold rounded-xl transition-all disabled:opacity-60">
                {submitting ? "Enviando..." : "Sim, estou ciente"}
              </button>
              <button onClick={() => setShowModal(false)} disabled={submitting}
                className="w-full py-2 text-sm text-gray-400 hover:text-gray-600">
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      <GrupoVoeturFooter />
    </div>
  );
}
