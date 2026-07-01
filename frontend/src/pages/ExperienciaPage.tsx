import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../lib/api";
import { useAuth } from "../context/AuthContext";

// ─── tipos ───────────────────────────────────────────────────────────────────

interface Colaborador {
  id: string | null;
  matricula: string;
  nome: string;
  cargo: string | null;
  empresa: string | null;
  departamento: string | null;
  gestor_nome: string | null;
  gestor_email: string | null;
}

interface AvaliacaoRow {
  id: string;
  tipo: string;
  data_prevista: string;
  status: string;
  total_envios: number;
  ultimo_envio_at: string | null;
  primeiro_envio_at: string | null;
  colaborador: Colaborador;
}

interface DetalheModal {
  avaliacao: {
    id: string;
    tipo: string;
    status: string;
    data_prevista: string;
    respostas: any;
    gestor_concordou: boolean;
    gestor_assinatura_at: string | null;
    gestor_ip: string | null;
    total_envios: number;
  };
  colaborador: Colaborador;
  email_log: {
    id: string;
    tipo_email: string;
    destinatario: string;
    enviado_at: string;
    sucesso: boolean;
  }[];
  formulario: any;
}

// ─── helpers ─────────────────────────────────────────────────────────────────

const TABS = [
  { id: "45",         label: "45 Dias" },
  { id: "90",         label: "90 Dias" },
  { id: "auditoria",  label: "Auditoria" },
  { id: "relatorios", label: "Relatórios" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const STATUS_BADGE: Record<string, { cls: string; label: string }> = {
  pendente:   { cls: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300", label: "Pendente"   },
  enviado:    { cls: "bg-blue-100   text-blue-800   dark:bg-blue-900/40   dark:text-blue-300",   label: "Enviado"    },
  respondido: { cls: "bg-green-100  text-green-800  dark:bg-green-900/40  dark:text-green-300",  label: "Respondido" },
  expirado:   { cls: "bg-red-100    text-red-800    dark:bg-red-900/40    dark:text-red-300",    label: "Expirado"   },
  sem_gestor: { cls: "bg-red-200    text-red-900    dark:bg-red-900/60    dark:text-red-200",    label: "Sem gestor" },
};

const PARECER_LABEL: Record<string, { cls: string; label: string }> = {
  seguir:      { cls: "text-green-700 dark:text-green-400", label: "Seguir por mais 45 dias" },
  interromper: { cls: "text-red-700   dark:text-red-400",   label: "Interromper nos 45 dias" },
  efetivar:    { cls: "text-green-700 dark:text-green-400", label: "Efetivação do colaborador" },
  encerrar:    { cls: "text-red-700   dark:text-red-400",   label: "Encerrar contrato"         },
};

const ESCALA_LABEL: Record<number, string> = { 1: "Não atende", 2: "Atende Parcialmente", 3: "Atende", 4: "Supera" };

const EMPRESA_ABREV: Record<string, string> = {
  "Voetur Cargas":                          "VTCLOG",
  "Voetur Turismo":                         "V Viagens",
  "BRASILIA EMPREENDIMENTOS IMOBILIARIOS":  "Brasília Imob.",
  "VIP SERVICE":                            "VIP Service",
  "VIP SERVICE AVIATION":                   "VIP Aviation",
  "VIP CARGAS":                             "VIP CARGAS",
  "VIP CARGAS RIO":                         "VIP C. Rio",
  "ANARAC EMPREENDIMENTOS":                 "Anarac",
  "LOCADORA":                               "Locadora",
  "Payfly":                                 "Payfly",
};
function abrevEmpresa(nome: string | null | undefined): string {
  if (!nome) return "—";
  return EMPRESA_ABREV[nome] ?? nome;
}

function Badge({ status }: { status: string }) {
  const b = STATUS_BADGE[status] ?? { cls: "bg-gray-100 text-gray-700", label: status };
  return <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${b.cls}`}>{b.label}</span>;
}

function fmt(dt: string | null) {
  if (!dt) return "—";
  return new Date(dt).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
function fmtDate(dt: string | null) {
  if (!dt) return "—";
  const [y, m, d] = dt.split("-");
  return `${d}/${m}/${y}`;
}

// ─── modal de detalhes ────────────────────────────────────────────────────────

function DetalheModalView({ detalhe, onClose }: { detalhe: DetalheModal; onClose: () => void }) {
  const av = detalhe.avaliacao;
  const emp = detalhe.colaborador;
  const r = av.respostas || {};
  const ind: Record<string, number> = r.indicadores || {};
  const parecer = r.parecer;
  const parecerInfo = parecer ? PARECER_LABEL[parecer] : null;
  const formulario = detalhe.formulario || {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>

        <div className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
          <div>
            <p className="font-bold text-gray-900 dark:text-gray-100">{emp?.nome}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Avaliação {av.tipo === "45_dias" ? "45 Dias" : "90 Dias"} · {emp?.empresa}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 text-2xl leading-none">&times;</button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* Info geral */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><p className="text-xs text-gray-500 dark:text-gray-400">Matrícula</p><p className="font-medium text-gray-900 dark:text-gray-100">{emp.matricula}</p></div>
            <div><p className="text-xs text-gray-500 dark:text-gray-400">Cargo</p><p className="font-medium text-gray-900 dark:text-gray-100">{emp.cargo || "—"}</p></div>
            <div><p className="text-xs text-gray-500 dark:text-gray-400">Gestor</p><p className="font-medium text-gray-900 dark:text-gray-100">{emp.gestor_nome || "—"}</p></div>
            <div><p className="text-xs text-gray-500 dark:text-gray-400">Status</p><Badge status={av.status} /></div>
          </div>

          {/* Assinatura digital */}
          {av.gestor_assinatura_at && (
            <div className="bg-[#E6F4F0] dark:bg-[#00694E]/15 rounded-xl p-4 border border-[#00694E]/20 text-sm">
              <p className="font-semibold text-[#00694E] dark:text-emerald-400 mb-1">Assinatura Digital</p>
              <p className="text-gray-800 dark:text-gray-200">Assinado em: <strong>{fmt(av.gestor_assinatura_at)}</strong></p>
              {av.gestor_ip && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">IP: {av.gestor_ip}</p>}
            </div>
          )}

          {/* Respostas — indicadores */}
          {Object.keys(ind).length > 0 && (
            <div>
              <p className="font-semibold text-gray-800 dark:text-gray-200 mb-3">Indicadores Avaliados</p>
              <div className="space-y-2">
                {(formulario.indicadores || Object.keys(ind).map((k) => ({ id: k, label: k }))).map((item: any) => {
                  const val = ind[item.id];
                  return val !== undefined ? (
                    <div key={item.id} className="flex items-center justify-between py-1.5 border-b border-gray-100 dark:border-gray-800 text-sm">
                      <span className="text-gray-700 dark:text-gray-300">{item.label}</span>
                      <span className={`font-semibold px-2 py-0.5 rounded text-xs ${
                        val === 4 ? "bg-emerald-100 text-emerald-800" :
                        val === 3 ? "bg-blue-100 text-blue-800" :
                        val === 2 ? "bg-amber-100 text-amber-800" :
                        "bg-red-100 text-red-800"}`}>
                        {val} — {ESCALA_LABEL[val]}
                      </span>
                    </div>
                  ) : null;
                })}
              </div>
            </div>
          )}

          {/* Campos de texto */}
          {[["Pontos de destaque", "pontos_destaque"], ["Pontos de melhoria", "pontos_melhoria"], ["Ações planejadas", "acoes_planejadas"]].map(([label, key]) =>
            r[key] ? (
              <div key={key}>
                <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">{label}</p>
                <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap bg-gray-50 dark:bg-gray-800 rounded-lg px-3 py-2">{r[key]}</p>
              </div>
            ) : null
          )}

          {/* Parecer */}
          {parecerInfo && (
            <div className="border-t border-gray-100 dark:border-gray-700 pt-4">
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">Parecer do Líder</p>
              <p className={`font-bold text-base ${parecerInfo.cls}`}>{parecerInfo.label}</p>
            </div>
          )}

          {/* Log de e-mails */}
          {detalhe.email_log.length > 0 && (
            <div>
              <p className="font-semibold text-gray-800 dark:text-gray-200 mb-2 text-sm">Histórico de E-mails ({detalhe.email_log.length})</p>
              <div className="space-y-1">
                {detalhe.email_log.map((log) => (
                  <div key={log.id} className="flex items-center justify-between text-xs py-1.5 border-b border-gray-100 dark:border-gray-800">
                    <div>
                      <span className={`font-semibold mr-2 ${log.sucesso ? "text-green-700 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>{log.sucesso ? "✓" : "✗"}</span>
                      <span className="text-gray-600 dark:text-gray-400 capitalize">{log.tipo_email.replace(/_/g, " ")}</span>
                      <span className="text-gray-400 ml-2">→ {log.destinatario}</span>
                    </div>
                    <span className="text-gray-400">{fmt(log.enviado_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── modal edição e-mail gestor ───────────────────────────────────────────────

function EditGestorModal({ avId, empId, gestorEmail, gestorNome, onClose, onSaved }:
  { avId: string; empId: string; gestorEmail: string; gestorNome: string; onClose: () => void; onSaved: () => void }) {
  const { token } = useAuth();
  const [email, setEmail] = useState(gestorEmail || "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const save = async () => {
    if (!email.trim()) { setErr("E-mail obrigatório"); return; }
    setSaving(true);
    try {
      await apiFetch(`/api/experiencia/admin/colaborador/${empId}/gestor-email`, {
        token,
        method: "PATCH",
        json: { gestor_email: email.trim() },
      });
      onSaved();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <p className="font-bold text-gray-900 dark:text-gray-100 mb-1">Corrigir E-mail do Gestor</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">{gestorNome}</p>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm
                     bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100
                     focus:outline-none focus:ring-2 focus:ring-[#00694E]/40 focus:border-[#00694E]"
          placeholder="email@empresa.com.br"
        />
        {err && <p className="text-red-600 text-xs mt-1">{err}</p>}
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">Cancelar</button>
          <button onClick={save} disabled={saving}
            className="flex-1 bg-[#00694E] hover:bg-[#004F3A] disabled:bg-gray-400 text-white font-semibold rounded-lg py-2 text-sm transition-colors">
            {saving ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── tabela dias ──────────────────────────────────────────────────────────────

function TabelaDias({
  tipo, empresa, setEmpresa, empresas,
}: {
  tipo: "45" | "90";
  empresa: string;
  setEmpresa: (e: string) => void;
  empresas: string[];
}) {
  const { token } = useAuth();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<AvaliacaoRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState("");
  const [detalhe, setDetalhe] = useState<DetalheModal | null>(null);
  const [editModal, setEditModal] = useState<{ avId: string; empId: string; gestorNome: string; gestorEmail: string } | null>(null);

  const tipoParam = tipo === "45" ? "45-dias" : "90-dias";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (empresa) params.set("empresa", empresa);
      if (status) params.set("status", status);
      if (q) params.set("q", q);
      const data = await apiFetch(`/api/experiencia/admin/${tipoParam}?${params}`, { token });
      setRows(data);
    } catch (e: any) {
      showToast("Erro ao carregar: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [tipoParam, empresa, status, q]);

  useEffect(() => { load(); }, [load]);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 4000);
  }

  async function handleEnviar(id: string) {
    try {
      await apiFetch(`/api/experiencia/admin/enviar/${id}`, { token, method: "POST" });
      showToast("Avaliação enviada!");
      load();
    } catch (e: any) { showToast("Erro: " + e.message); }
  }

  async function handleReenviar(id: string) {
    try {
      await apiFetch(`/api/experiencia/admin/reenviar/${id}`, { token, method: "POST" });
      showToast("Cobrança reenviada!");
      load();
    } catch (e: any) { showToast("Erro: " + e.message); }
  }

  async function handleDisparar() {
    if (!window.confirm(`Disparar cobranças para todos os pendentes${empresa ? ` da empresa "${empresa}"` : ""}?`)) return;
    try {
      const body: any = { tipo: `${tipo}_dias` };
      if (empresa) body.empresa = empresa;
      const r = await apiFetch("/api/experiencia/admin/disparar-cobracas", {
        token,
        method: "POST",
        json: body,
      });
      showToast(`${r.enviados ?? 0} cobrança(s) disparada(s)!`);
      load();
    } catch (e: any) { showToast("Erro: " + e.message); }
  }

  async function handleVerRespostas(id: string) {
    try {
      const data = await apiFetch(`/api/experiencia/admin/auditoria/${id}/detalhes`, { token });
      setDetalhe(data);
    } catch (e: any) { showToast("Erro: " + e.message); }
  }

  const pendentesCount = rows.filter((r) => ["pendente", "enviado"].includes(r.status)).length;

  return (
    <div>
      {toast && (
        <div className="mb-4 bg-[#E6F4F0] dark:bg-[#00694E]/15 border border-[#00694E]/20 text-[#00694E] dark:text-emerald-400 rounded-lg px-4 py-2 text-sm font-medium">{toast}</div>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select value={empresa} onChange={(e) => setEmpresa(e.target.value)}
          className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40">
          <option value="">Todas as empresas</option>
          {empresas.map((emp) => <option key={emp} value={emp}>{emp}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40">
          <option value="">Todos os status</option>
          <option value="pendente">Pendente</option>
          <option value="enviado">Enviado</option>
          <option value="respondido">Respondido</option>
          <option value="expirado">Expirado</option>
          <option value="sem_gestor">Sem gestor</option>
        </select>
        <input type="text" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar colaborador ou matrícula..."
          className="flex-1 min-w-[200px] border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40" />
        <button onClick={load} className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800">Atualizar</button>
        {pendentesCount > 0 && (
          <button onClick={handleDisparar}
            className="ml-auto bg-amber-500 hover:bg-amber-600 text-white font-semibold rounded-lg px-4 py-1.5 text-sm flex items-center gap-2 transition-colors">
            <span>🔔</span>
            Disparar cobranças ({pendentesCount})
          </button>
        )}
      </div>

      {/* Tabela */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
        <table className="min-w-full text-xs">
          <thead className="bg-gray-50 dark:bg-gray-800 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            <tr>
              {["Empresa", "Mat.", "Colaborador", "Cargo", "Gestor Imediato", "E-mail Gestor", `Data ${tipo}d`, "Status", "Env.", "Último envio", "Ações"].map((h) => (
                <th key={h} className="px-2 py-2 text-left whitespace-nowrap font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? (
              <tr><td colSpan={11} className="px-3 py-8 text-center text-gray-400">Carregando...</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={11} className="px-3 py-8 text-center text-gray-400">Nenhum registro encontrado</td></tr>
            ) : rows.map((row) => {
              const emp = row.colaborador;
              const semGestor = !emp?.gestor_email;
              return (
                <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <td className="px-2 py-2 whitespace-nowrap text-gray-700 dark:text-gray-300" title={emp?.empresa ?? ""}>{abrevEmpresa(emp?.empresa)}</td>
                  <td className="px-2 py-2 font-mono text-gray-600 dark:text-gray-400 whitespace-nowrap">{emp?.matricula}</td>
                  <td className="px-2 py-2 font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">{emp?.nome}</td>
                  <td className="px-2 py-2 text-gray-600 dark:text-gray-400 whitespace-nowrap">{emp?.cargo || "—"}</td>
                  <td className="px-2 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{emp?.gestor_nome || <span className="text-red-500 font-semibold">Sem gestor</span>}</td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1">
                      {semGestor
                        ? <span className="text-red-500 font-semibold">sem e-mail</span>
                        : <span className="text-gray-600 dark:text-gray-400 max-w-[130px] truncate block" title={emp?.gestor_email ?? ""}>{emp?.gestor_email}</span>
                      }
                      <button
                        onClick={() => setEditModal({ avId: row.id, empId: emp?.id ?? "", gestorNome: emp?.gestor_nome || "", gestorEmail: emp?.gestor_email || "" })}
                        className="text-[#00694E] hover:text-[#004F3A] shrink-0"
                        title="Corrigir e-mail">✏️</button>
                    </div>
                  </td>
                  <td className="px-2 py-2 whitespace-nowrap font-medium text-gray-900 dark:text-gray-100">{fmtDate(row.data_prevista)}</td>
                  <td className="px-2 py-2"><Badge status={row.status} /></td>
                  <td className="px-2 py-2 text-center text-gray-600 dark:text-gray-400">{row.total_envios}</td>
                  <td className="px-2 py-2 whitespace-nowrap text-gray-500 dark:text-gray-400">{fmt(row.ultimo_envio_at)}</td>
                  <td className="px-2 py-2 whitespace-nowrap">
                    <div className="flex gap-1">
                      {row.status === "pendente" && !semGestor && (
                        <button onClick={() => handleEnviar(row.id)}
                          className="px-2 py-1 bg-[#00694E] hover:bg-[#004F3A] text-white rounded text-xs font-semibold transition-colors">
                          Enviar
                        </button>
                      )}
                      {row.status === "enviado" && (
                        <button onClick={() => handleReenviar(row.id)}
                          className="px-2 py-1 bg-amber-500 hover:bg-amber-600 text-white rounded text-xs font-semibold transition-colors">
                          Reenviar
                        </button>
                      )}
                      {row.status === "respondido" && (
                        <button onClick={() => handleVerRespostas(row.id)}
                          className="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold transition-colors">
                          Ver resp.
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 mt-2">{rows.length} registro(s)</p>

      {detalhe && <DetalheModalView detalhe={detalhe} onClose={() => setDetalhe(null)} />}
      {editModal && (
        <EditGestorModal
          avId={editModal.avId}
          empId={editModal.empId ?? ""}
          gestorNome={editModal.gestorNome}
          gestorEmail={editModal.gestorEmail}
          onClose={() => setEditModal(null)}
          onSaved={() => { setEditModal(null); load(); }}
        />
      )}
    </div>
  );
}

// ─── aba auditoria ────────────────────────────────────────────────────────────

function TabAuditoria({ empresa, setEmpresa, empresas }:
  { empresa: string; setEmpresa: (e: string) => void; empresas: string[] }) {
  const { token } = useAuth();
  const [tipo, setTipo] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  const [rows, setRows] = useState<AvaliacaoRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [detalhe, setDetalhe] = useState<DetalheModal | null>(null);
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (empresa) params.set("empresa", empresa);
      if (tipo) params.set("tipo", tipo);
      if (status) params.set("status", status);
      if (q) params.set("q", q);
      if (dataInicio) params.set("data_inicio", dataInicio);
      if (dataFim) params.set("data_fim", dataFim);
      const data = await apiFetch(`/api/experiencia/admin/auditoria?${params}`, { token });
      setRows(data);
    } catch (e: any) {
      setToast("Erro: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [empresa, tipo, status, q, dataInicio, dataFim]);

  useEffect(() => { load(); }, [load]);

  async function handleVer(id: string) {
    try {
      const data = await apiFetch(`/api/experiencia/admin/auditoria/${id}/detalhes`, { token });
      setDetalhe(data);
    } catch (e: any) { setToast("Erro: " + e.message); }
  }

  return (
    <div>
      {toast && <div className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm">{toast}</div>}

      <div className="flex flex-wrap gap-3 mb-4">
        <select value={empresa} onChange={(e) => setEmpresa(e.target.value)}
          className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40">
          <option value="">Todas as empresas</option>
          {empresas.map((emp) => <option key={emp} value={emp}>{emp}</option>)}
        </select>
        <select value={tipo} onChange={(e) => setTipo(e.target.value)}
          className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40">
          <option value="">Todos os tipos</option>
          <option value="45_dias">45 Dias</option>
          <option value="90_dias">90 Dias</option>
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40">
          <option value="">Todos os status</option>
          <option value="respondido">Respondido</option>
          <option value="enviado">Enviado</option>
          <option value="pendente">Pendente</option>
          <option value="expirado">Expirado</option>
        </select>
        <input type="text" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Colaborador, matrícula ou gestor..."
          className="flex-1 min-w-[200px] border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40" />
        <input type="date" value={dataInicio} onChange={(e) => setDataInicio(e.target.value)}
          className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40" />
        <input type="date" value={dataFim} onChange={(e) => setDataFim(e.target.value)}
          className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40" />
        <button onClick={load} className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800">Buscar</button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            <tr>
              {["Empresa", "Colaborador", "Tipo", "Gestor", "Data Prevista", "Respondido em", "Assinado em", "Envios", "Status", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left whitespace-nowrap font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? (
              <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-400">Carregando...</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-400">Nenhum resultado</td></tr>
            ) : rows.map((row) => {
              const emp = row.colaborador;
              const av = row as any;
              return (
                <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <td className="px-4 py-3 whitespace-nowrap">{emp?.empresa || "—"}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900 dark:text-gray-100">{emp?.nome}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 font-mono">{emp?.matricula}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${row.tipo === "45_dias" ? "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300" : "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300"}`}>
                      {row.tipo === "45_dias" ? "45 Dias" : "90 Dias"}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-gray-900 dark:text-gray-100">{emp?.gestor_nome || "—"}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-gray-900 dark:text-gray-100">{fmtDate(row.data_prevista)}</td>
                  <td className="px-4 py-3 text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap">{fmt(av.gestor_assinatura_at)}</td>
                  <td className="px-4 py-3 text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap">{fmt(av.gestor_assinatura_at)}</td>
                  <td className="px-4 py-3 text-center">{row.total_envios}</td>
                  <td className="px-4 py-3"><Badge status={row.status} /></td>
                  <td className="px-4 py-3">
                    <button onClick={() => handleVer(row.id)}
                      className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold transition-colors whitespace-nowrap">
                      Ver avaliação
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 mt-2">{rows.length} registro(s)</p>

      {detalhe && <DetalheModalView detalhe={detalhe} onClose={() => setDetalhe(null)} />}
    </div>
  );
}

// ─── aba relatórios ───────────────────────────────────────────────────────────

function TabRelatorios({ empresa, empresas }: { empresa: string; empresas: string[] }) {
  const { token } = useAuth();
  const [empFilt, setEmpFilt] = useState(empresa);
  const [tipo, setTipo] = useState("");
  const [status, setStatus] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [toast, setToast] = useState("");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 4000);
  }

  async function handleSync() {
    if (!window.confirm("Disparar sincronização manual com o Benner agora?")) return;
    setSyncing(true);
    try {
      const r = await apiFetch("/api/experiencia/admin/sync-benner", { token, method: "POST" });
      showToast(`Sync concluído: ${r.novos ?? 0} novo(s), ${r.atualizados ?? 0} atualizado(s)`);
    } catch (e: any) {
      showToast("Erro no sync: " + e.message);
    } finally {
      setSyncing(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (empFilt) params.set("empresa", empFilt);
      if (tipo) params.set("tipo", tipo);
      if (status) params.set("status", status);
      const exportToken = localStorage.getItem("auth_token") ?? "";
      const API = import.meta.env.VITE_API_URL ?? "";
      const resp = await fetch(`${API}/api/experiencia/admin/export?${params}`, {
        headers: { Authorization: `Bearer ${exportToken}` },
      });
      if (!resp.ok) throw new Error("Falha ao exportar");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `avaliacoes_experiencia_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      showToast("Erro: " + e.message);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-6">
      {toast && <div className="bg-[#E6F4F0] dark:bg-[#00694E]/15 border border-[#00694E]/20 text-[#00694E] dark:text-emerald-400 rounded-lg px-4 py-2 text-sm font-medium">{toast}</div>}

      {/* Sync manual */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">Sincronização Benner</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Sync automático às 03h00 · Sincroniza novos admitidos e atualiza gestores
        </p>
        <button onClick={handleSync} disabled={syncing}
          className="bg-[#00694E] hover:bg-[#004F3A] disabled:bg-gray-400 text-white font-semibold rounded-lg px-5 py-2 text-sm transition-colors">
          {syncing ? "Sincronizando..." : "Sincronizar agora"}
        </button>
      </div>

      {/* Exportação */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">Exportar Avaliações</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">Exporta CSV com todos os registros (filtros opcionais)</p>
        <div className="flex flex-wrap gap-3 mb-4">
          <select value={empFilt} onChange={(e) => setEmpFilt(e.target.value)}
            className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40">
            <option value="">Todas as empresas</option>
            {empresas.map((emp) => <option key={emp} value={emp}>{emp}</option>)}
          </select>
          <select value={tipo} onChange={(e) => setTipo(e.target.value)}
            className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40">
            <option value="">Todos os tipos</option>
            <option value="45_dias">45 Dias</option>
            <option value="90_dias">90 Dias</option>
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)}
            className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]/40">
            <option value="">Todos os status</option>
            <option value="respondido">Respondido</option>
            <option value="enviado">Enviado</option>
            <option value="pendente">Pendente</option>
            <option value="expirado">Expirado</option>
          </select>
        </div>
        <button onClick={handleExport} disabled={exporting}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold rounded-lg px-5 py-2 text-sm transition-colors flex items-center gap-2">
          <span>⬇</span>
          {exporting ? "Gerando CSV..." : "Exportar CSV"}
        </button>
      </div>

      {/* Legenda */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Escala de Avaliação</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { val: 1, cls: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",             label: "Não atende"          },
            { val: 2, cls: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300", label: "Atende Parcialmente" },
            { val: 3, cls: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",     label: "Atende"              },
            { val: 4, cls: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300", label: "Supera" },
          ].map((s) => (
            <div key={s.val} className={`rounded-lg p-3 text-center ${s.cls}`}>
              <p className="text-2xl font-bold">{s.val}</p>
              <p className="text-xs font-semibold mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── página principal ─────────────────────────────────────────────────────────

export default function ExperienciaPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState<TabId>("45");
  const [empresa, setEmpresa] = useState("");
  const [empresas, setEmpresas] = useState<string[]>([]);

  useEffect(() => {
    if (!token) return;
    apiFetch("/api/experiencia/admin/empresas", { token })
      .then((data) => setEmpresas(data as string[]))
      .catch(() => {});
  }, [token]);

  return (
    <div className="p-6 max-w-screen-2xl mx-auto">
      {/* Cabeçalho */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Avaliação de Experiência</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Gerenciamento das avaliações de 45 e 90 dias — VPA.RH.PGP.09 v04</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-5 py-2.5 text-sm font-semibold rounded-t-lg transition-colors border-b-2 ${
                tab === t.id
                  ? "border-[#00694E] text-[#00694E] bg-[#E6F4F0]/60 dark:bg-[#00694E]/10"
                  : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Conteúdo */}
      {tab === "45" && (
        <TabelaDias tipo="45" empresa={empresa} setEmpresa={setEmpresa} empresas={empresas} />
      )}
      {tab === "90" && (
        <TabelaDias tipo="90" empresa={empresa} setEmpresa={setEmpresa} empresas={empresas} />
      )}
      {tab === "auditoria" && (
        <TabAuditoria empresa={empresa} setEmpresa={setEmpresa} empresas={empresas} />
      )}
      {tab === "relatorios" && (
        <TabRelatorios empresa={empresa} empresas={empresas} />
      )}
    </div>
  );
}
