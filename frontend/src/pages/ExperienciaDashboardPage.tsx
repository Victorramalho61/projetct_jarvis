import { Fragment, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../lib/api";
import { useAuth } from "../context/AuthContext";

// ─── tipos (espelham GET /api/experiencia/admin/dashboard) ───────────────────

type Colaborador = {
  id: string | null; matricula: string; nome: string; cargo: string | null; empresa: string | null;
  departamento: string | null; data_admissao: string | null; gestor_nome: string | null;
  gestor_email: string | null; gestor_direto_nome: string | null; gestor_email_origem: string | null;
  gestor_manual: boolean | null; estrutura: string | null;
};

type Linha = {
  id: string; tipo: string; status: string; data_prevista: string; total_envios: number;
  ultimo_envio_at: string | null; gestor_assinatura_at: string | null; parecer: string | null;
  nota_total: number | null; nota_percentual: number | null; nota_insuficiente: boolean | null;
  envio_automatico_at: string | null; kpis: string[]; colaborador: Colaborador;
};

type Grupo = { nome: string; total: number; respondidas: number; nota_insuficiente: number };

type Dashboard = {
  kpis: { id: string; label: string; total: number }[];
  totais: { avaliacoes: number; respondidas: number; pct_respondidas: number | null; nota_media_pct: number | null; por_tipo: Record<string, number> };
  pareceres: Record<string, number>;
  por_empresa: Grupo[];
  por_departamento: Grupo[];
  linhas: Linha[];
};

const KPI_COR: Record<string, string> = {
  vencendo_10d: "border-amber-300 text-amber-700 dark:text-amber-300",
  pendentes_envio: "border-gray-300 text-gray-700 dark:text-gray-200",
  aguardando_resposta: "border-blue-300 text-blue-700 dark:text-blue-300",
  vencidas: "border-red-300 text-red-700 dark:text-red-300",
  sem_gestor: "border-orange-300 text-orange-700 dark:text-orange-300",
  respondidas_prazo: "border-green-300 text-green-700 dark:text-green-300",
  respondidas_atraso: "border-yellow-300 text-yellow-700 dark:text-yellow-300",
  nota_insuficiente: "border-red-500 text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20",
};

const STATUS_LABEL: Record<string, string> = {
  pendente: "Pendente", enviado: "Enviado", respondido: "Respondido", expirado: "Expirado", sem_gestor: "Sem gestor",
};
const PARECER_LABEL: Record<string, string> = {
  seguir: "Seguir (45 dias)", interromper: "Interromper (45 dias)", efetivar: "Efetivar (90 dias)", encerrar: "Encerrar (90 dias)",
};

function fmtData(iso: string | null | undefined) {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

function Barras({ titulo, itens }: { titulo: string; itens: Grupo[] }) {
  const max = Math.max(1, ...itens.map((i) => i.total));
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">{titulo}</h3>
      <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
        {itens.map((i) => (
          <div key={i.nome} className="text-xs">
            <div className="flex justify-between gap-2 text-gray-600 dark:text-gray-300">
              <span className="truncate" title={i.nome}>{i.nome}</span>
              <span className="shrink-0 tabular-nums">
                {i.respondidas}/{i.total} respondidas
                {i.nota_insuficiente > 0 && <span className="ml-1 font-semibold text-red-600 dark:text-red-400">· {i.nota_insuficiente} insuf.</span>}
              </span>
            </div>
            <div className="mt-1 flex h-2 gap-[2px] overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
              <div className="h-2 rounded-full bg-[#00694E]" style={{ width: `${(100 * i.respondidas) / max}%` }} />
              <div className="h-2 rounded-full bg-gray-300 dark:bg-gray-600" style={{ width: `${(100 * (i.total - i.respondidas)) / max}%` }} />
            </div>
          </div>
        ))}
        {itens.length === 0 && <p className="text-xs text-gray-400">Sem dados.</p>}
      </div>
    </div>
  );
}

function Detalhe({ l }: { l: Linha }) {
  const c = l.colaborador;
  const campo = (rotulo: string, valor: React.ReactNode) => (
    <div><p className="text-[11px] text-gray-500 dark:text-gray-400">{rotulo}</p><p className="text-sm text-gray-900 dark:text-gray-100">{valor || "—"}</p></div>
  );
  return (
    <div className="grid grid-cols-2 gap-3 bg-gray-50 dark:bg-gray-800/60 p-4 sm:grid-cols-4">
      {campo("Matrícula", c.matricula)}
      {campo("Cargo", c.cargo)}
      {campo("Departamento", c.departamento)}
      {campo("Empresa", c.empresa)}
      {campo("Admissão", fmtData(c.data_admissao))}
      {campo("Avaliação", `${l.tipo === "45_dias" ? "45" : "90"} dias · vence ${fmtData(l.data_prevista)}`)}
      {campo("Gestor (recebe o e-mail)", <>{c.gestor_nome}<br /><span className="text-xs text-gray-500">{c.gestor_email}</span></>)}
      {campo("Chefe direto na estrutura", c.gestor_direto_nome ? `${c.gestor_direto_nome}${c.gestor_email_origem === "superior" ? " (sem e-mail corporativo)" : ""}` : null)}
      {campo("Envios", `${l.total_envios}${l.ultimo_envio_at ? ` · último ${fmtData(l.ultimo_envio_at)}` : ""}${l.envio_automatico_at ? " · automático" : ""}`)}
      {campo("Respondido em", fmtData(l.gestor_assinatura_at))}
      {campo("Parecer", l.parecer ? PARECER_LABEL[l.parecer] ?? l.parecer : null)}
      {campo("Nota", l.nota_total != null ? `${l.nota_total}/36 (${l.nota_percentual}%)` : null)}
    </div>
  );
}

function ListaModal({ titulo, linhas, onClose }: { titulo: string; linhas: Linha[]; onClose: () => void }) {
  const [aberta, setAberta] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const filtradas = useMemo(() => {
    const b = busca.trim().toLowerCase();
    return b ? linhas.filter((l) => [l.colaborador.nome, l.colaborador.matricula, l.colaborador.gestor_nome, l.colaborador.departamento]
      .some((v) => (v ?? "").toLowerCase().includes(b))) : linhas;
  }, [linhas, busca]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div className="flex max-h-[90vh] w-full max-w-6xl flex-col rounded-2xl bg-white shadow-2xl dark:bg-gray-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-gray-100 p-5 dark:border-gray-800">
          <div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">{titulo}</h3>
            <p className="text-xs text-gray-500">{filtradas.length} colaborador(es) · clique para ver os dados</p>
          </div>
          <button onClick={onClose} className="grid h-8 w-8 place-items-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-800">✕</button>
        </div>
        <div className="px-5 pt-4">
          <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar colaborador, matrícula, gestor, departamento…"
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 sm:w-96" />
        </div>
        <div className="flex-1 overflow-auto p-5">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-50 text-left text-[11px] uppercase tracking-wider text-gray-500 dark:bg-gray-800 dark:text-gray-400">
              <tr>
                <th className="px-3 py-2">Colaborador</th><th className="px-3 py-2">Departamento</th><th className="px-3 py-2">Empresa</th>
                <th className="px-3 py-2">Gestor</th><th className="px-3 py-2">Tipo</th><th className="px-3 py-2">Vencimento</th>
                <th className="px-3 py-2">Status</th><th className="px-3 py-2 text-right">Nota</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {filtradas.map((l) => (
                <Fragment key={l.id}>
                  <tr onClick={() => setAberta(aberta === l.id ? null : l.id)}
                    className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/40">
                    <td className="px-3 py-2 font-medium text-gray-900 dark:text-gray-100">{l.colaborador.nome}</td>
                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{l.colaborador.departamento || "—"}</td>
                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{l.colaborador.empresa || "—"}</td>
                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{l.colaborador.gestor_nome || <span className="text-red-500">sem gestor</span>}</td>
                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{l.tipo === "45_dias" ? "45 dias" : "90 dias"}</td>
                    <td className="px-3 py-2 tabular-nums text-gray-600 dark:text-gray-300">{fmtData(l.data_prevista)}</td>
                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{STATUS_LABEL[l.status] ?? l.status}</td>
                    <td className={`px-3 py-2 text-right tabular-nums ${l.nota_insuficiente ? "font-bold text-red-600 dark:text-red-400" : "text-gray-600 dark:text-gray-300"}`}>
                      {l.nota_percentual != null ? `${l.nota_percentual}%` : "—"}
                    </td>
                  </tr>
                  {aberta === l.id && (
                    <tr><td colSpan={8} className="p-0"><Detalhe l={l} /></td></tr>
                  )}
                </Fragment>
              ))}
              {filtradas.length === 0 && <tr><td colSpan={8} className="px-3 py-8 text-center text-gray-400">Nenhum colaborador.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function ExperienciaDashboardPage() {
  const { token } = useAuth();
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [empresas, setEmpresas] = useState<string[]>([]);
  const [departamentos, setDepartamentos] = useState<string[]>([]);
  const [f, setF] = useState({ tipo: "", empresa: "", departamento: "", data_inicio: "", data_fim: "" });
  const [drill, setDrill] = useState<{ titulo: string; linhas: Linha[] } | null>(null);

  useEffect(() => {
    apiFetch<string[]>("/api/experiencia/admin/empresas", { token }).then(setEmpresas).catch(() => {});
    apiFetch<string[]>("/api/experiencia/admin/departamentos", { token }).then(setDepartamentos).catch(() => {});
  }, [token]);

  useEffect(() => {
    setLoading(true);
    const p = new URLSearchParams();
    Object.entries(f).forEach(([k, v]) => { if (v) p.set(k, v); });
    apiFetch<Dashboard>(`/api/experiencia/admin/dashboard?${p}`, { token })
      .then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [f, token]);

  const abrir = (id: string, titulo: string) => {
    if (!data) return;
    setDrill({ titulo, linhas: data.linhas.filter((l) => l.kpis.includes(id)) });
  };

  const sel = "rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm text-gray-800 dark:text-gray-200";

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Avaliação de Experiência — Dashboard</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">Avaliações de 45 e 90 dias. Clique em um indicador para ver os colaboradores.</p>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
        <select value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })} className={sel}>
          <option value="">45 e 90 dias</option><option value="45_dias">45 dias</option><option value="90_dias">90 dias</option>
        </select>
        <select value={f.empresa} onChange={(e) => setF({ ...f, empresa: e.target.value })} className={sel}>
          <option value="">Todas as empresas</option>{empresas.map((e) => <option key={e} value={e}>{e}</option>)}
        </select>
        <select value={f.departamento} onChange={(e) => setF({ ...f, departamento: e.target.value })} className={`${sel} max-w-[220px]`}>
          <option value="">Todos os departamentos</option>{departamentos.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <label className="text-xs text-gray-500">Vencimento de</label>
        <input type="date" value={f.data_inicio} onChange={(e) => setF({ ...f, data_inicio: e.target.value })} className={sel} />
        <label className="text-xs text-gray-500">até</label>
        <input type="date" value={f.data_fim} onChange={(e) => setF({ ...f, data_fim: e.target.value })} className={sel} />
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><div className="h-8 w-8 animate-spin rounded-full border-4 border-[#00694E] border-t-transparent" /></div>
      ) : !data ? (
        <div className="rounded-xl border border-gray-200 p-8 text-center text-gray-500 dark:border-gray-800">Nenhum dado disponível.</div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {data.kpis.map((k) => (
              <button key={k.id} onClick={() => abrir(k.id, k.label)} disabled={k.total === 0}
                className={`rounded-xl border-2 bg-white p-4 text-left transition hover:shadow-md disabled:cursor-default disabled:opacity-60 dark:bg-gray-900 ${KPI_COR[k.id] ?? ""}`}>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{k.label}</p>
                <p className="mt-1 text-3xl font-extrabold tabular-nums">{k.total}</p>
                {k.total > 0 && <p className="mt-1 text-[11px] text-gray-400">ver colaboradores →</p>}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Avaliações no período", data.totais.avaliacoes],
              ["Respondidas", `${data.totais.respondidas} (${data.totais.pct_respondidas ?? 0}%)`],
              ["Nota média", data.totais.nota_media_pct != null ? `${data.totais.nota_media_pct}%` : "—"],
              ["45 / 90 dias", `${data.totais.por_tipo["45_dias"] ?? 0} / ${data.totais.por_tipo["90_dias"] ?? 0}`],
            ].map(([rot, val]) => (
              <div key={rot as string} className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
                <p className="text-xs text-gray-500 dark:text-gray-400">{rot}</p>
                <p className="mt-1 text-xl font-bold tabular-nums text-gray-900 dark:text-gray-100">{val}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Barras titulo="Por empresa" itens={data.por_empresa} />
            <Barras titulo="Por departamento" itens={data.por_departamento} />
            <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
              <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">Pareceres dos gestores</h3>
              {Object.keys(data.pareceres).length === 0 ? (
                <p className="text-xs text-gray-400">Nenhuma avaliação respondida no período.</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {Object.entries(data.pareceres).map(([p, n]) => (
                    <li key={p} className="flex justify-between text-gray-700 dark:text-gray-300">
                      <span>{PARECER_LABEL[p] ?? p}</span><span className="font-semibold tabular-nums">{n}</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-4 text-[11px] text-gray-400">
                Nota insuficiente: inferior a 50% da nota total (18 de 36 pontos). O RH recebe alerta por e-mail em rh@voetur.com.br.
              </p>
            </div>
          </div>
        </>
      )}

      {drill && <ListaModal titulo={drill.titulo} linhas={drill.linhas} onClose={() => setDrill(null)} />}
    </div>
  );
}
