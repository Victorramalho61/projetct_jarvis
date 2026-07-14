const SCORE_MAP: Record<number, { label: string; desc: string; color: string }> = {
  5: { label: "EE",  desc: "Excede as Expectativas",              color: "bg-purple-100 text-purple-700 border-purple-300 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-700" },
  4: { label: "SE",  desc: "Supera as Expectativas",              color: "bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-700" },
  3: { label: "AE",  desc: "Atende as Expectativas",              color: "bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700" },
  2: { label: "APE", desc: "Atende Parcialmente as Expectativas", color: "bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700" },
  1: { label: "NAE", desc: "Não Atende às Expectativas",          color: "bg-red-100 text-red-700 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700" },
};

export function ScoreBadge({ score }: { score: number }) {
  const rounded = Math.round(score);
  const s = SCORE_MAP[rounded];
  if (!s)
    return (
      <span className="px-2 py-1 rounded border text-xs font-semibold bg-gray-100 text-gray-700 border-gray-300">
        {score}
      </span>
    );
  return (
    <span className={`px-3 py-1 rounded-full border text-xs font-bold ${s.color}`}>
      {s.label} <span className="font-normal">— {s.desc}</span>
    </span>
  );
}

export function avgLabel(avg: number): string {
  if (avg >= 4.5) return "Excede as Expectativas";
  if (avg >= 3.5) return "Supera as Expectativas";
  if (avg >= 2.5) return "Atende as Expectativas";
  if (avg >= 1.5) return "Atende Parcialmente";
  return "Não Atende às Expectativas";
}

// ── Painel de resultado (reutilizado na tela pública de ciência e na visão interna do RH) ──
export function ResultPanel({
  data, primaryBg, primaryText, primaryBorder, acknowledged, acknowledgedAt, onOpenModal,
}: {
  data: any; primaryBg: string; primaryText: string; primaryBorder: string;
  acknowledged: boolean; acknowledgedAt?: string; onOpenModal?: () => void;
}) {
  function formatDate(iso: string) {
    try { return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
    catch { return iso; }
  }

  return (
    <div className="space-y-4">
      {/* Banner */}
      <div className={`${primaryBg} text-white rounded-2xl shadow-lg overflow-hidden`}>
        <div className="h-1 bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500" />
        <div className="p-6">
          <p className="text-white/70 text-xs font-semibold uppercase tracking-widest mb-1">
            Resultado da Avaliação de Desempenho
          </p>
          <h1 className="text-xl font-bold mb-1">{data.cycle_name}</h1>
          <p className="text-white/80 text-sm mt-2">
            Olá, <strong>{data.employee_name}</strong>
          </p>
        </div>
      </div>

      {/* Ciência já registrada — banner informativo (não bloqueia visualização) */}
      {acknowledged && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl p-4 flex items-center gap-3">
          <svg className="w-5 h-5 text-green-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="text-sm font-semibold text-green-800 dark:text-green-200">Ciência já registrada</p>
            {acknowledgedAt && (
              <p className="text-xs text-green-600 dark:text-green-400 mt-0.5">
                em {formatDate(acknowledgedAt)}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Avaliador */}
      <div className={`bg-white dark:bg-gray-800 rounded-2xl p-4 shadow border-l-4 ${primaryBorder} flex items-center gap-3`}>
        <div className="w-9 h-9 rounded-full bg-[#E6F4F0] dark:bg-[#00694E]/20 flex items-center justify-center flex-shrink-0">
          <svg className={`w-5 h-5 ${primaryText}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        </div>
        <div>
          <p className="text-xs text-gray-500">Avaliado por</p>
          <p className="font-semibold text-gray-900 dark:text-white">{data.evaluator_name}</p>
        </div>
      </div>

      {/* Notas por indicador */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-gray-100 dark:border-gray-700 overflow-hidden">
        <div className={`${primaryBg} px-5 py-3`}>
          <h3 className="text-white font-bold text-sm uppercase tracking-wide">Notas por Indicador</h3>
        </div>
        <div className="divide-y divide-gray-50 dark:divide-gray-700">
          {data.indicator_scores?.map((s: any) => {
            const wasCalibrated = s.calibrated_score != null;
            const displayScore = wasCalibrated ? s.calibrated_score : s.score;
            return (
              <div key={s.indicator_id}>
                <div className="flex items-center justify-between px-5 py-3 gap-3">
                  <span className="text-sm text-gray-700 dark:text-gray-300 flex-1 min-w-0">{s.indicator_name}</span>
                  <div className="flex items-center gap-2">
                    {s.self_score != null && (
                      <span className="text-[10px] font-semibold text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-900/20 px-2 py-0.5 rounded-full whitespace-nowrap">
                        Auto: {s.self_score}
                      </span>
                    )}
                    <ScoreBadge score={displayScore} />
                  </div>
                </div>
                {wasCalibrated ? (
                  <div className="px-5 pb-3 -mt-1 space-y-1.5">
                    <div className="bg-amber-50 dark:bg-amber-900/20 rounded-lg px-3 py-2 border-l-2 border-amber-400 dark:border-amber-600">
                      <p className="text-[10px] font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wide mb-0.5">
                        🟧 RH realizou a calibragem desta nota
                      </p>
                      {s.calibrated_justification && (
                        <p className="text-xs text-amber-800 dark:text-amber-300 italic leading-relaxed">"{s.calibrated_justification}"</p>
                      )}
                    </div>
                    <details className="group">
                      <summary className="cursor-pointer text-[11px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 select-none list-none flex items-center gap-1">
                        <span className="group-open:rotate-90 transition-transform inline-block">▸</span> Ver nota/comentário original do gestor
                      </summary>
                      <div className="mt-1.5 bg-gray-50 dark:bg-gray-700/40 rounded-lg px-3 py-2 border-l-2 border-blue-300 dark:border-blue-700">
                        <p className="text-[10px] font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-0.5">🟦 Nota original do gestor: {s.score}</p>
                        <p className="text-xs text-gray-600 dark:text-gray-400 italic leading-relaxed">
                          {s.justification ? `"${s.justification}"` : "Sem comentários do gestor"}
                        </p>
                      </div>
                    </details>
                  </div>
                ) : s.justification && (
                  <div className="px-5 pb-3 -mt-1">
                    <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg px-3 py-2 border-l-2 border-blue-300 dark:border-blue-700">
                      <p className="text-[10px] font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-0.5">
                        🟦 Comentário do Gestor
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400 italic leading-relaxed">
                        "{s.justification}"
                      </p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Notas finais — gestor, auto-avaliação e combinada */}
      <div className={`bg-white dark:bg-gray-800 rounded-2xl p-5 shadow border-2 ${primaryBorder}`}>
        <div className="flex items-center justify-between">
          <div>
            <span className="font-bold text-gray-900 dark:text-white text-lg">Nota Final (Gestor)</span>
            <p className="text-xs text-gray-400 mt-0.5">{avgLabel(data.final_score ?? 0)}</p>
          </div>
          <div className="text-right">
            <span className={`text-3xl font-black ${primaryText} dark:text-blue-400`}>
              {data.final_score?.toFixed(2)}
            </span>
            <span className="text-sm text-gray-400 ml-1">/ 5,00</span>
          </div>
        </div>
        {data.nota_final_combinada != null && (
          <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-600 dark:text-gray-300">Nota Final (média avaliação + auto-avaliação)</span>
            <span className="text-xl font-black text-blue-700 dark:text-blue-400">
              {Number(data.nota_final_combinada).toFixed(2)} <span className="text-sm text-gray-400 font-normal">/ 5,00</span>
            </span>
          </div>
        )}
      </div>

      {/* Comentários — Gestor / Colaborador / RH, empilhados e coloridos */}
      <div className="space-y-3">
        {data.was_calibrated ? (
          <details className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-gray-100 dark:border-gray-700 overflow-hidden group">
            <summary className="cursor-pointer bg-gray-50 dark:bg-gray-700/50 px-5 py-3 select-none list-none flex items-center gap-2">
              <span className="group-open:rotate-90 transition-transform inline-block text-gray-400">▸</span>
              <h3 className="text-sm font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
                🟦 Ver comentário original do gestor
              </h3>
            </summary>
            <div className="px-5 py-4">
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
                {data.observations || "Sem comentários do gestor"}
              </p>
            </div>
          </details>
        ) : data.observations && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-blue-100 dark:border-blue-900/40 overflow-hidden">
            <div className="bg-blue-50 dark:bg-blue-900/20 px-5 py-3">
              <h3 className="text-sm font-bold text-blue-700 dark:text-blue-400 uppercase tracking-wide">
                🟦 Comentários sobre o desempenho do colaborador
              </h3>
            </div>
            <div className="px-5 py-4">
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
                {data.observations}
              </p>
            </div>
          </div>
        )}

        {data.self_observations && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-violet-100 dark:border-violet-900/40 overflow-hidden">
            <div className="bg-violet-50 dark:bg-violet-900/20 px-5 py-3">
              <h3 className="text-sm font-bold text-violet-700 dark:text-violet-400 uppercase tracking-wide">
                🟪 Comentários sobre seu desempenho (auto avaliação)
              </h3>
            </div>
            <div className="px-5 py-4">
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
                {data.self_observations}
              </p>
            </div>
          </div>
        )}

        {data.was_calibrated && data.calibration_notes && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-amber-100 dark:border-amber-900/40 overflow-hidden">
            <div className="bg-amber-50 dark:bg-amber-900/20 px-5 py-3">
              <h3 className="text-sm font-bold text-amber-700 dark:text-amber-400 uppercase tracking-wide">
                🟧 Comentário do RH (calibragem)
              </h3>
            </div>
            <div className="px-5 py-4">
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
                {data.calibration_notes}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Botão de ciência — apenas se ainda não registrou */}
      {!acknowledged && onOpenModal && (
        <button
          onClick={onOpenModal}
          className="w-full py-4 bg-green-600 hover:bg-green-700 text-white font-bold text-lg rounded-2xl shadow-lg transition-all"
        >
          ✓ Dar Ciência da Avaliação
        </button>
      )}

      {/* Se já confirmou — botão desativado para clareza */}
      {acknowledged && (
        <div className="w-full py-4 bg-gray-100 dark:bg-gray-700/50 text-gray-400 dark:text-gray-500 font-semibold text-base rounded-2xl text-center border border-gray-200 dark:border-gray-700">
          ✓ Ciência registrada — obrigado(a)
        </div>
      )}
    </div>
  );
}
