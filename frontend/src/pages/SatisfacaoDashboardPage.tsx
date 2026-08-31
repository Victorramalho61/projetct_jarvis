import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";
import KPICard from "../components/freshservice/KPICard";

type Campanha = {
  id: string;
  ano: number;
  titulo: string;
  status: string;
  data_prazo?: string;
  total_convidados?: number;
  total_respondidos?: number;
};

type PerguntaDashboard = {
  campanha_pergunta_id: string;
  pergunta_id: string;
  ordem: number;
  texto: string;
  total_respostas: number;
  media: number | null;
  distribuicao: Record<string, number>;
  percentual_ruim: number;
  alerta_plano_acao: boolean;
  pendentes_triagem: number;
  planos_acao: any[];
};

type Dashboard = {
  campanha: Campanha;
  envio: { total_convidados: number; total_enviados: number; percentual_enviado: number };
  aderencia: { total_convidados: number; total_respondidos: number; percentual: number; atingiu_minimo: boolean };
  notas_gerais: {
    total_avaliacoes: number; media: number | null; distribuicao: Record<string, number>;
    percentual_ruim: number; percentual_neutro: number; percentual_bom: number;
  };
  dias_restantes: number | null;
  perguntas: PerguntaDashboard[];
};

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

function Badge({ children, color = "gray" }: { children: React.ReactNode; color?: string }) {
  const map: Record<string, string> = {
    gray:  "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
    green: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    red:   "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    amber: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  };
  return <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${map[color] ?? map.gray}`}>{children}</span>;
}

function ModalWrapper({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b border-gray-100 dark:border-gray-700">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="h-8 w-8 grid place-items-center rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700 transition-all">✕</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function pctColor(pct: number): "red" | "amber" | "green" {
  if (pct > 30) return "red";
  if (pct >= 15) return "amber";
  return "green";
}

export default function SatisfacaoDashboardPage() {
  const { token } = useAuth();
  const [campanhas, setCampanhas] = useState<Campanha[]>([]);
  const [campanhaId, setCampanhaId] = useState<string>("");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [historico, setHistorico] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detalhe, setDetalhe] = useState<PerguntaDashboard | null>(null);
  const [triagemItens, setTriagemItens] = useState<any[]>([]);

  useEffect(() => {
    apiFetch<Campanha[]>("/api/satisfacao/admin/campanhas", { token })
      .then((rows) => {
        setCampanhas(rows);
        if (rows.length) setCampanhaId(rows[0].id);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erro ao carregar campanhas"))
      .finally(() => setLoading(false));

    apiFetch<any[]>("/api/satisfacao/admin/dashboard/historico", { token })
      .then(setHistorico)
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!campanhaId) return;
    apiFetch<Dashboard>(`/api/satisfacao/admin/campanhas/${campanhaId}/dashboard`, { token })
      .then(setDashboard)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erro ao carregar dashboard"));
  }, [campanhaId, token]);

  async function abrirDetalhe(p: PerguntaDashboard) {
    setDetalhe(p);
    try {
      const itens = await apiFetch<any[]>(`/api/satisfacao/admin/campanhas/${campanhaId}/triagem`, { token });
      setTriagemItens(itens.filter((i) => i.campanha_pergunta_id === p.campanha_pergunta_id));
    } catch {
      setTriagemItens([]);
    }
  }

  const totalPlanosAbertos = (dashboard?.perguntas ?? [])
    .flatMap((p) => p.planos_acao)
    .filter((pl: any) => pl.status !== "concluido").length;

  const chartData = historico.map((h) => ({
    ano: h.ano,
    media: h.media_geral,
    ...h.medias_por_categoria,
  }));

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Pesquisa de Satisfação — Dashboard</h1>
        {campanhas.length > 0 && (
          <select
            value={campanhaId}
            onChange={(e) => setCampanhaId(e.target.value)}
            className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          >
            {campanhas.map((c) => (
              <option key={c.id} value={c.id}>{c.titulo} ({c.status})</option>
            ))}
          </select>
        )}
      </div>

      {loading && <p className="text-sm text-gray-400">Carregando...</p>}
      {error && <p className="text-sm text-red-500">{error}</p>}

      {!loading && !error && campanhas.length === 0 && (
        <Card className="p-8 text-center">
          <p className="text-gray-500 dark:text-gray-400 mb-3">Nenhuma campanha de pesquisa foi criada ainda.</p>
          <a href="/satisfacao/envio" className="text-sm font-semibold text-[#00694E] hover:underline">
            Ir para Envio e Tratamento para criar a primeira campanha →
          </a>
        </Card>
      )}

      {dashboard && (
        <>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-2">Funil de envio</p>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
              <KPICard label="Convidados" value={dashboard.envio.total_convidados} />
              <KPICard
                label="% Enviados"
                value={`${dashboard.envio.percentual_enviado}%`}
                sub={`${dashboard.envio.total_enviados} de ${dashboard.envio.total_convidados}`}
              />
              <KPICard
                label="% Respondidos"
                value={`${dashboard.aderencia.percentual}%`}
                sub={dashboard.aderencia.atingiu_minimo ? "Meta de 30% atingida" : "Abaixo da meta de 30%"}
                colorClass={dashboard.aderencia.atingiu_minimo ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}
              />
              <KPICard label="Dias restantes" value={dashboard.dias_restantes ?? "—"} />
              <KPICard label="Planos de ação abertos" value={totalPlanosAbertos} colorClass={totalPlanosAbertos > 0 ? "text-amber-600 dark:text-amber-400" : undefined} />
            </div>
          </div>

          <Card className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-3">Satisfação Geral</p>
            <div className="flex items-center gap-6 flex-wrap">
              <div>
                <p className="text-4xl font-bold text-gray-900 dark:text-gray-100">{dashboard.notas_gerais.media ?? "—"}</p>
                <p className="text-xs text-gray-400 mt-1">{dashboard.notas_gerais.total_avaliacoes} avaliações no total</p>
              </div>
              <div className="flex-1 min-w-[220px]">
                <div className="flex gap-1 h-4 rounded-full overflow-hidden mb-2">
                  {dashboard.notas_gerais.percentual_ruim > 0 && (
                    <div className="bg-red-400" style={{ width: `${dashboard.notas_gerais.percentual_ruim}%` }} title="Ruim (notas 1-2)" />
                  )}
                  {dashboard.notas_gerais.percentual_neutro > 0 && (
                    <div className="bg-amber-400" style={{ width: `${dashboard.notas_gerais.percentual_neutro}%` }} title="Neutro (nota 3)" />
                  )}
                  {dashboard.notas_gerais.percentual_bom > 0 && (
                    <div className="bg-green-500" style={{ width: `${dashboard.notas_gerais.percentual_bom}%` }} title="Bom (notas 4-5)" />
                  )}
                  {dashboard.notas_gerais.total_avaliacoes === 0 && <div className="bg-gray-100 dark:bg-gray-700 w-full" />}
                </div>
                <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400 flex-wrap">
                  <span>🔴 Ruim: {dashboard.notas_gerais.percentual_ruim}%</span>
                  <span>🟡 Neutro: {dashboard.notas_gerais.percentual_neutro}%</span>
                  <span>🟢 Bom: {dashboard.notas_gerais.percentual_bom}%</span>
                </div>
              </div>
            </div>
          </Card>

          <div className="grid gap-4">
            {dashboard.perguntas.map((p) => (
              <Card key={p.campanha_pergunta_id} className="p-5">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="flex-1 min-w-[240px]">
                    <p className="font-semibold text-gray-900 dark:text-gray-100">{p.texto}</p>
                    <p className="text-xs text-gray-400 mt-1">{p.total_respostas} respostas · média {p.media ?? "—"}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {p.pendentes_triagem > 0 && <Badge color="amber">{p.pendentes_triagem} triagem pendente</Badge>}
                    <Badge color={pctColor(p.percentual_ruim)}>{p.percentual_ruim}% notas ruins</Badge>
                    {p.alerta_plano_acao && p.planos_acao.filter((pl) => pl.status !== "concluido").length === 0 && (
                      <Badge color="red">Plano de ação pendente</Badge>
                    )}
                    <button
                      onClick={() => abrirDetalhe(p)}
                      className="text-xs font-medium text-[#00694E] hover:underline"
                    >
                      Ver detalhes
                    </button>
                  </div>
                </div>
                <div className="mt-3 flex gap-1 h-3 rounded-full overflow-hidden">
                  {[1, 2, 3, 4, 5].map((n) => {
                    const qtd = p.distribuicao[String(n)] || 0;
                    const pctBar = p.total_respostas ? (qtd / p.total_respostas) * 100 : 0;
                    const cor = n <= 2 ? "bg-red-400" : n === 3 ? "bg-amber-400" : "bg-green-500";
                    return pctBar > 0 ? <div key={n} className={cor} style={{ width: `${pctBar}%` }} title={`Nota ${n}: ${qtd}`} /> : null;
                  })}
                  {p.total_respostas === 0 && <div className="bg-gray-100 dark:bg-gray-700 w-full" />}
                </div>
              </Card>
            ))}
          </div>

          {chartData.length > 1 && (
            <Card className="p-5">
              <h3 className="font-bold text-gray-900 dark:text-gray-100 mb-4">Comparativo Anual — Média Geral</h3>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="ano" />
                  <YAxis domain={[1, 5]} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="media" name="Média geral" stroke="#00694E" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}
        </>
      )}

      <ModalWrapper open={!!detalhe} onClose={() => setDetalhe(null)} title={detalhe?.texto ?? ""}>
        {detalhe && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><p className="text-gray-400 text-xs">Média</p><p className="font-semibold text-gray-900 dark:text-gray-100">{detalhe.media ?? "—"}</p></div>
              <div><p className="text-gray-400 text-xs">% Notas ruins</p><p className="font-semibold text-gray-900 dark:text-gray-100">{detalhe.percentual_ruim}%</p></div>
            </div>
            <div>
              <h4 className="font-semibold text-sm text-gray-700 dark:text-gray-300 mb-2">Comentários pendentes de triagem</h4>
              {triagemItens.length === 0 && <p className="text-xs text-gray-400">Nenhum comentário pendente de triagem.</p>}
              <div className="space-y-2">
                {triagemItens.map((i) => (
                  <div key={i.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-sm">
                    <p className="font-semibold text-red-600 dark:text-red-400">Nota {i.nota} — {(i.sat_respostas?.sat_clientes || {}).empresa_nome}</p>
                    <p className="text-gray-600 dark:text-gray-400 text-xs mt-1">{i.comentario || "Sem comentário"}</p>
                  </div>
                ))}
              </div>
            </div>
            {detalhe.planos_acao.length > 0 && (
              <div>
                <h4 className="font-semibold text-sm text-gray-700 dark:text-gray-300 mb-2">Planos de ação</h4>
                <div className="space-y-2">
                  {detalhe.planos_acao.map((pl: any) => (
                    <div key={pl.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-sm flex items-center justify-between">
                      <span className="text-gray-700 dark:text-gray-300">{pl.descricao}</span>
                      <Badge color={pl.status === "concluido" ? "green" : pl.status === "em_andamento" ? "amber" : "red"}>{pl.status}</Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </ModalWrapper>
    </div>
  );
}
