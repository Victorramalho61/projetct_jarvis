import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";

type Campanha = {
  id: string; ano: number; titulo: string; status: string;
  data_inicio?: string; data_prazo?: string; qtd_postergacoes: number;
  total_convidados?: number; total_respondidos?: number;
};

type Resposta = {
  id: string; status: string; canal_resposta?: string; total_envios: number;
  ultimo_envio_at?: string; respondido_at?: string;
  sat_clientes: { id: string; empresa_nome: string; contato_nome: string; contato_email: string };
};

type CampanhaPergunta = { id: string; ordem: number; texto_snapshot: string };

type TriagemItem = {
  id: string; nota: number; comentario: string | null;
  sat_respostas: { sat_clientes: { empresa_nome: string; contato_nome: string } };
  sat_campanha_perguntas: { texto_snapshot: string; pergunta_id: string };
};

type PlanoAcao = {
  id: string; pergunta_id: string; descricao: string; responsavel: string;
  prazo: string; status: string; percentual_notas_ruins: number;
};

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm ${className}`}>{children}</div>;
}

function Badge({ children, color = "gray" }: { children: React.ReactNode; color?: string }) {
  const map: Record<string, string> = {
    gray:  "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
    green: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    red:   "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    amber: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    blue:  "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  };
  return <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${map[color] ?? map.gray}`}>{children}</span>;
}

function statusColor(s: string) {
  return s === "respondido" ? "green" : s === "expirado" ? "red" : s === "enviado" ? "blue" : "gray";
}

function ModalWrapper({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b border-gray-100 dark:border-gray-700">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="h-8 w-8 grid place-items-center rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700 transition-all">✕</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

const TABS = [
  { id: "campanha", label: "Campanha" },
  { id: "respostas", label: "Respostas" },
  { id: "triagem", label: "Triagem" },
  { id: "planos", label: "Planos de Ação" },
] as const;
type TabId = typeof TABS[number]["id"];

export default function SatisfacaoEnvioPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState<TabId>("campanha");
  const [campanhas, setCampanhas] = useState<Campanha[]>([]);
  const [campanhaId, setCampanhaId] = useState<string>("");
  const [novoAno, setNovoAno] = useState(new Date().getFullYear());
  const [novoTitulo, setNovoTitulo] = useState(`Pesquisa de Satisfação ${new Date().getFullYear()}`);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [respostas, setRespostas] = useState<Resposta[]>([]);
  const [campanhaPerguntas, setCampanhaPerguntas] = useState<CampanhaPergunta[]>([]);
  const [triagem, setTriagem] = useState<TriagemItem[]>([]);
  const [planos, setPlanos] = useState<PlanoAcao[]>([]);

  const [lancarManual, setLancarManual] = useState<Resposta | null>(null);
  const [notasManuais, setNotasManuais] = useState<Record<string, { nota: number; comentario: string }>>({});

  const [triagemAtiva, setTriagemAtiva] = useState<TriagemItem | null>(null);
  const [pontosAvaliacao, setPontosAvaliacao] = useState<any[]>([]);
  const [pontoSelecionado, setPontoSelecionado] = useState("");
  const [observacaoTriagem, setObservacaoTriagem] = useState("");

  const [novoPlano, setNovoPlano] = useState<{ pergunta_id: string; descricao: string; responsavel: string; prazo: string } | null>(null);

  const campanha = campanhas.find((c) => c.id === campanhaId);

  function reloadCampanhas() {
    apiFetch<Campanha[]>("/api/satisfacao/admin/campanhas", { token })
      .then((rows) => {
        setCampanhas(rows);
        if (rows.length && !campanhaId) setCampanhaId(rows[0].id);
      })
      .catch((e) => setMsg(e instanceof ApiError ? e.message : "Erro ao carregar campanhas"));
  }

  useEffect(reloadCampanhas, [token]);

  useEffect(() => {
    if (!campanhaId) return;
    apiFetch<Resposta[]>(`/api/satisfacao/admin/campanhas/${campanhaId}/respostas`, { token }).then(setRespostas).catch(() => {});
    apiFetch<TriagemItem[]>(`/api/satisfacao/admin/campanhas/${campanhaId}/triagem`, { token }).then(setTriagem).catch(() => {});
    apiFetch<PlanoAcao[]>(`/api/satisfacao/admin/campanhas/${campanhaId}/planos-acao`, { token }).then(setPlanos).catch(() => {});
    apiFetch<any>(`/api/satisfacao/admin/campanhas/${campanhaId}/dashboard`, { token })
      .then((d) => setCampanhaPerguntas((d.perguntas || []).map((p: any) => ({ id: p.campanha_pergunta_id, ordem: p.ordem, texto_snapshot: p.texto }))))
      .catch(() => {});
  }, [campanhaId, token]);

  async function criarCampanha() {
    setBusy(true); setMsg(null);
    try {
      await apiFetch("/api/satisfacao/admin/campanhas", { method: "POST", token, json: { ano: novoAno, titulo: novoTitulo } });
      setMsg("Campanha criada.");
      reloadCampanhas();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao criar campanha"); }
    setBusy(false);
  }

  async function iniciarCampanha() {
    if (!campanhaId) return;
    setBusy(true); setMsg(null);
    try {
      const r = await apiFetch<any>(`/api/satisfacao/admin/campanhas/${campanhaId}/iniciar`, { method: "POST", token, json: {} });
      setMsg(`Campanha iniciada. ${r.enviados} e-mails enviados, ${r.erros} erros. Prazo: ${r.data_prazo}`);
      reloadCampanhas();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao iniciar campanha"); }
    setBusy(false);
  }

  async function postergarCampanha() {
    if (!campanhaId) return;
    const motivo = window.prompt("Motivo da postergação (opcional):") || undefined;
    setBusy(true); setMsg(null);
    try {
      const r = await apiFetch<any>(`/api/satisfacao/admin/campanhas/${campanhaId}/postergar`, { method: "POST", token, json: { motivo } });
      setMsg(`Prazo postergado para ${r.data_prazo}.`);
      reloadCampanhas();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao postergar"); }
    setBusy(false);
  }

  async function encerrarCampanha() {
    if (!campanhaId) return;
    if (!window.confirm("Encerrar a campanha agora? Respostas pendentes serão marcadas como expiradas.")) return;
    setBusy(true); setMsg(null);
    try {
      await apiFetch(`/api/satisfacao/admin/campanhas/${campanhaId}/encerrar`, { method: "POST", token, json: {} });
      setMsg("Campanha encerrada.");
      reloadCampanhas();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao encerrar"); }
    setBusy(false);
  }

  async function reenviar(respostaId: string) {
    try {
      await apiFetch(`/api/satisfacao/admin/respostas/${respostaId}/reenviar`, { method: "POST", token, json: {} });
      setMsg("Cobrança reenviada.");
      apiFetch<Resposta[]>(`/api/satisfacao/admin/campanhas/${campanhaId}/respostas`, { token }).then(setRespostas);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao reenviar"); }
  }

  async function salvarLancamentoManual() {
    if (!lancarManual) return;
    const itens = campanhaPerguntas.map((cp) => ({
      campanha_pergunta_id: cp.id,
      nota: notasManuais[cp.id]?.nota ?? 3,
      comentario: notasManuais[cp.id]?.comentario || undefined,
    }));
    try {
      await apiFetch(`/api/satisfacao/admin/respostas/${lancarManual.id}/lancar-manual`, { method: "POST", token, json: { itens } });
      setMsg("Resposta lançada manualmente.");
      setLancarManual(null); setNotasManuais({});
      apiFetch<Resposta[]>(`/api/satisfacao/admin/campanhas/${campanhaId}/respostas`, { token }).then(setRespostas);
      apiFetch<TriagemItem[]>(`/api/satisfacao/admin/campanhas/${campanhaId}/triagem`, { token }).then(setTriagem);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao lançar resposta"); }
  }

  async function abrirTriagem(item: TriagemItem) {
    setTriagemAtiva(item); setPontoSelecionado(""); setObservacaoTriagem("");
    try {
      const pontos = await apiFetch<any[]>(`/api/satisfacao/cadastro/perguntas/${item.sat_campanha_perguntas.pergunta_id}/pontos-avaliacao`, { token });
      setPontosAvaliacao(pontos);
    } catch { setPontosAvaliacao([]); }
  }

  async function salvarTriagem() {
    if (!triagemAtiva || !pontoSelecionado) return;
    try {
      await apiFetch(`/api/satisfacao/admin/respostas-itens/${triagemAtiva.id}/triagem`, {
        method: "POST", token, json: { ponto_avaliacao_id: pontoSelecionado, observacao: observacaoTriagem || undefined },
      });
      setTriagemAtiva(null);
      apiFetch<TriagemItem[]>(`/api/satisfacao/admin/campanhas/${campanhaId}/triagem`, { token }).then(setTriagem);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao classificar"); }
  }

  async function criarPlanoAcao() {
    if (!novoPlano) return;
    try {
      await apiFetch(`/api/satisfacao/admin/campanhas/${campanhaId}/planos-acao`, { method: "POST", token, json: novoPlano });
      setNovoPlano(null);
      apiFetch<PlanoAcao[]>(`/api/satisfacao/admin/campanhas/${campanhaId}/planos-acao`, { token }).then(setPlanos);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao criar plano de ação"); }
  }

  async function atualizarStatusPlano(planoId: string, status: string) {
    try {
      await apiFetch(`/api/satisfacao/admin/planos-acao/${planoId}`, { method: "PATCH", token, json: { status } });
      apiFetch<PlanoAcao[]>(`/api/satisfacao/admin/campanhas/${campanhaId}/planos-acao`, { token }).then(setPlanos);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao atualizar plano"); }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Pesquisa de Satisfação — Envio e Tratamento</h1>
        {campanhas.length > 0 && (
          <select value={campanhaId} onChange={(e) => setCampanhaId(e.target.value)}
            className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100">
            {campanhas.map((c) => <option key={c.id} value={c.id}>{c.titulo} ({c.status})</option>)}
          </select>
        )}
      </div>

      {msg && <div className="text-sm bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded-lg px-4 py-2">{msg}</div>}

      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t.id ? "border-[#00694E] text-[#00694E]" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "campanha" && (
        <Card className="p-5 space-y-5">
          <div>
            <h3 className="font-bold text-gray-900 dark:text-gray-100 mb-3">Criar campanha do ano</h3>
            <div className="flex gap-3 flex-wrap items-end">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Ano</label>
                <input type="number" value={novoAno} onChange={(e) => setNovoAno(Number(e.target.value))}
                  className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm w-28 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
              </div>
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs text-gray-500 mb-1">Título</label>
                <input type="text" value={novoTitulo} onChange={(e) => setNovoTitulo(e.target.value)}
                  className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm w-full bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
              </div>
              <button disabled={busy} onClick={criarCampanha} className="bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold px-4 py-2 rounded-lg text-sm disabled:opacity-50">
                Criar
              </button>
            </div>
          </div>

          {campanha && (
            <div className="border-t border-gray-100 dark:border-gray-700 pt-5">
              <h3 className="font-bold text-gray-900 dark:text-gray-100 mb-2">{campanha.titulo}</h3>
              <div className="flex gap-3 text-sm text-gray-500 mb-4 flex-wrap">
                <Badge color={campanha.status === "encerrada" ? "gray" : campanha.status === "postergada" ? "amber" : "blue"}>{campanha.status}</Badge>
                {campanha.data_inicio && <span>Início: {campanha.data_inicio}</span>}
                {campanha.data_prazo && <span>Prazo: {campanha.data_prazo}</span>}
                <span>Postergações: {campanha.qtd_postergacoes}</span>
                <span>{campanha.total_respondidos ?? 0}/{campanha.total_convidados ?? 0} respondidos</span>
              </div>
              <div className="flex gap-2 flex-wrap">
                {campanha.status === "rascunho" && (
                  <button disabled={busy} onClick={iniciarCampanha} className="bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold px-4 py-2 rounded-lg text-sm disabled:opacity-50">Iniciar</button>
                )}
                {(campanha.status === "em_andamento" || campanha.status === "postergada") && (
                  <>
                    <button disabled={busy} onClick={postergarCampanha} className="bg-amber-500 hover:bg-amber-600 text-white font-semibold px-4 py-2 rounded-lg text-sm disabled:opacity-50">Postergar +10 dias úteis</button>
                    <button disabled={busy} onClick={encerrarCampanha} className="bg-red-500 hover:bg-red-600 text-white font-semibold px-4 py-2 rounded-lg text-sm disabled:opacity-50">Encerrar</button>
                  </>
                )}
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === "respostas" && (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900/50 text-left text-gray-500 dark:text-gray-400">
              <tr>
                <th className="p-3">Empresa</th><th className="p-3">Contato</th><th className="p-3">Status</th>
                <th className="p-3">Canal</th><th className="p-3">Envios</th><th className="p-3">Ações</th>
              </tr>
            </thead>
            <tbody className="text-gray-700 dark:text-gray-300">
              {respostas.map((r) => (
                <tr key={r.id} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="p-3">{r.sat_clientes.empresa_nome}</td>
                  <td className="p-3">{r.sat_clientes.contato_nome}</td>
                  <td className="p-3"><Badge color={statusColor(r.status)}>{r.status}</Badge></td>
                  <td className="p-3 text-xs text-gray-400">{r.canal_resposta || "—"}</td>
                  <td className="p-3">{r.total_envios}</td>
                  <td className="p-3 flex gap-2">
                    {r.status !== "respondido" && (
                      <>
                        <button onClick={() => reenviar(r.id)} className="text-xs text-[#00694E] hover:underline">Reenviar</button>
                        <button onClick={() => setLancarManual(r)} className="text-xs text-gray-500 hover:underline">Lançar manual</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {respostas.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-gray-400">Nenhuma resposta ainda.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}

      {tab === "triagem" && (
        <div className="space-y-3">
          {triagem.length === 0 && <p className="text-sm text-gray-400">Nenhum item pendente de triagem.</p>}
          {triagem.map((i) => (
            <Card key={i.id} className="p-4 flex items-start justify-between gap-4">
              <div>
                <p className="font-semibold text-red-600 dark:text-red-400">Nota {i.nota} — {(i.sat_respostas?.sat_clientes || {}).empresa_nome}</p>
                <p className="text-xs text-gray-500 mt-1">{i.sat_campanha_perguntas.texto_snapshot}</p>
                <p className="text-sm text-gray-700 dark:text-gray-300 mt-2">{i.comentario || "Sem comentário"}</p>
              </div>
              <button onClick={() => abrirTriagem(i)} className="bg-[#00694E] text-white text-xs font-semibold px-3 py-2 rounded-lg whitespace-nowrap">Classificar</button>
            </Card>
          ))}
        </div>
      )}

      {tab === "planos" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setNovoPlano({ pergunta_id: campanhaPerguntas[0]?.id ?? "", descricao: "", responsavel: "", prazo: "" })}
              className="bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold px-4 py-2 rounded-lg text-sm">Novo plano de ação</button>
          </div>
          {planos.length === 0 && <p className="text-sm text-gray-400">Nenhum plano de ação criado.</p>}
          {planos.map((p) => (
            <Card key={p.id} className="p-4 flex items-start justify-between gap-4 flex-wrap">
              <div>
                <p className="font-semibold text-gray-900 dark:text-gray-100">{p.descricao}</p>
                <p className="text-xs text-gray-500 mt-1">Responsável: {p.responsavel} · Prazo: {p.prazo} · {p.percentual_notas_ruins}% notas ruins</p>
              </div>
              <select value={p.status} onChange={(e) => atualizarStatusPlano(p.id, e.target.value)}
                className="border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1 text-xs bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100">
                <option value="aberto">Aberto</option>
                <option value="em_andamento">Em andamento</option>
                <option value="concluido">Concluído</option>
              </select>
            </Card>
          ))}
        </div>
      )}

      <ModalWrapper open={!!lancarManual} onClose={() => setLancarManual(null)} title="Lançar resposta manual">
        {lancarManual && (
          <div className="space-y-4">
            <p className="text-sm text-gray-500">{lancarManual.sat_clientes.empresa_nome} — {lancarManual.sat_clientes.contato_nome}</p>
            {campanhaPerguntas.map((cp) => (
              <div key={cp.id} className="border-t border-gray-100 dark:border-gray-700 pt-3">
                <p className="text-sm font-medium text-gray-800 dark:text-gray-200 mb-2">{cp.texto_snapshot}</p>
                <div className="flex gap-2 mb-2">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button key={n} type="button"
                      onClick={() => setNotasManuais((prev) => ({ ...prev, [cp.id]: { ...prev[cp.id], nota: n, comentario: prev[cp.id]?.comentario || "" } }))}
                      className={`h-8 w-8 rounded-lg text-xs font-bold border-2 ${notasManuais[cp.id]?.nota === n ? "border-[#00694E] bg-[#E6F4F0] text-[#00694E]" : "border-gray-200 dark:border-gray-600 text-gray-500"}`}>
                      {n}
                    </button>
                  ))}
                </div>
                <input type="text" placeholder="Comentário (opcional)"
                  value={notasManuais[cp.id]?.comentario || ""}
                  onChange={(e) => setNotasManuais((prev) => ({ ...prev, [cp.id]: { ...prev[cp.id], nota: prev[cp.id]?.nota || 3, comentario: e.target.value } }))}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
              </div>
            ))}
            <button onClick={salvarLancamentoManual} className="w-full bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold py-2 rounded-lg text-sm">Salvar</button>
          </div>
        )}
      </ModalWrapper>

      <ModalWrapper open={!!triagemAtiva} onClose={() => setTriagemAtiva(null)} title="Classificar causa-raiz">
        {triagemAtiva && (
          <div className="space-y-3">
            <p className="text-sm text-gray-600 dark:text-gray-400">{triagemAtiva.comentario || "Sem comentário"}</p>
            <select value={pontoSelecionado} onChange={(e) => setPontoSelecionado(e.target.value)}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100">
              <option value="">Selecione o ponto de avaliação...</option>
              {pontosAvaliacao.map((p) => <option key={p.id} value={p.id}>{p.titulo}</option>)}
            </select>
            <textarea placeholder="Observação (opcional)" value={observacaoTriagem} onChange={(e) => setObservacaoTriagem(e.target.value)}
              rows={3} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <button disabled={!pontoSelecionado} onClick={salvarTriagem} className="w-full bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold py-2 rounded-lg text-sm disabled:opacity-50">Salvar classificação</button>
          </div>
        )}
      </ModalWrapper>

      <ModalWrapper open={!!novoPlano} onClose={() => setNovoPlano(null)} title="Novo plano de ação">
        {novoPlano && (
          <div className="space-y-3">
            <select value={novoPlano.pergunta_id} onChange={(e) => setNovoPlano({ ...novoPlano, pergunta_id: e.target.value })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100">
              {campanhaPerguntas.map((cp) => <option key={cp.id} value={cp.id}>{cp.texto_snapshot}</option>)}
            </select>
            <textarea placeholder="Descrição do plano de ação" value={novoPlano.descricao} onChange={(e) => setNovoPlano({ ...novoPlano, descricao: e.target.value })}
              rows={3} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <input type="text" placeholder="Responsável" value={novoPlano.responsavel} onChange={(e) => setNovoPlano({ ...novoPlano, responsavel: e.target.value })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <input type="date" value={novoPlano.prazo} onChange={(e) => setNovoPlano({ ...novoPlano, prazo: e.target.value })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <button onClick={criarPlanoAcao} className="w-full bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold py-2 rounded-lg text-sm">Criar</button>
          </div>
        )}
      </ModalWrapper>
    </div>
  );
}
