import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";

type Cliente = {
  id: string; empresa_nome: string; contato_nome: string; contato_cargo?: string;
  contato_email: string; contato_telefone?: string; ativo: boolean; observacoes?: string;
};

type Pergunta = { id: string; ordem: number; texto: string; categoria?: string; ativa: boolean };

type PontoAvaliacao = { id: string; titulo: string; descricao: string; ordem: number; ativo: boolean };

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm ${className}`}>{children}</div>;
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

const SUBTABS = [
  { id: "clientes", label: "Clientes" },
  { id: "perguntas", label: "Perguntas" },
] as const;
type SubTabId = typeof SUBTABS[number]["id"];

export default function SatisfacaoCadastroPage() {
  const { token } = useAuth();
  const [subtab, setSubtab] = useState<SubTabId>("clientes");
  const [msg, setMsg] = useState<string | null>(null);

  // Clientes
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [clienteEdit, setClienteEdit] = useState<Partial<Cliente> | null>(null);

  // Perguntas
  const [perguntas, setPerguntas] = useState<Pergunta[]>([]);
  const [perguntaEdit, setPerguntaEdit] = useState<Partial<Pergunta> | null>(null);
  const [perguntaSelecionada, setPerguntaSelecionada] = useState<Pergunta | null>(null);
  const [pontos, setPontos] = useState<PontoAvaliacao[]>([]);
  const [pontoEdit, setPontoEdit] = useState<Partial<PontoAvaliacao> | null>(null);

  function reloadClientes() {
    apiFetch<Cliente[]>("/api/satisfacao/cadastro/clientes", { token }).then(setClientes).catch((e) => setMsg(e instanceof ApiError ? e.message : "Erro"));
  }
  function reloadPerguntas() {
    apiFetch<Pergunta[]>("/api/satisfacao/cadastro/perguntas", { token }).then(setPerguntas).catch((e) => setMsg(e instanceof ApiError ? e.message : "Erro"));
  }

  useEffect(() => { reloadClientes(); reloadPerguntas(); }, [token]);

  useEffect(() => {
    if (!perguntaSelecionada) return;
    apiFetch<PontoAvaliacao[]>(`/api/satisfacao/cadastro/perguntas/${perguntaSelecionada.id}/pontos-avaliacao`, { token }).then(setPontos).catch(() => {});
  }, [perguntaSelecionada, token]);

  async function salvarCliente() {
    if (!clienteEdit) return;
    try {
      if (clienteEdit.id) {
        await apiFetch(`/api/satisfacao/cadastro/clientes/${clienteEdit.id}`, { method: "PATCH", token, json: clienteEdit });
      } else {
        await apiFetch("/api/satisfacao/cadastro/clientes", { method: "POST", token, json: clienteEdit });
      }
      setClienteEdit(null);
      reloadClientes();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao salvar cliente"); }
  }

  async function desativarCliente(id: string) {
    if (!window.confirm("Desativar este cliente?")) return;
    try { await apiFetch(`/api/satisfacao/cadastro/clientes/${id}`, { method: "DELETE", token }); reloadClientes(); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao desativar"); }
  }

  async function salvarPergunta() {
    if (!perguntaEdit) return;
    try {
      if (perguntaEdit.id) {
        await apiFetch(`/api/satisfacao/cadastro/perguntas/${perguntaEdit.id}`, { method: "PATCH", token, json: perguntaEdit });
      } else {
        await apiFetch("/api/satisfacao/cadastro/perguntas", { method: "POST", token, json: perguntaEdit });
      }
      setPerguntaEdit(null);
      reloadPerguntas();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao salvar pergunta"); }
  }

  async function desativarPergunta(id: string) {
    if (!window.confirm("Desativar esta pergunta?")) return;
    try { await apiFetch(`/api/satisfacao/cadastro/perguntas/${id}`, { method: "DELETE", token }); reloadPerguntas(); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao desativar"); }
  }

  async function salvarPonto() {
    if (!pontoEdit || !perguntaSelecionada) return;
    try {
      if (pontoEdit.id) {
        await apiFetch(`/api/satisfacao/cadastro/pontos-avaliacao/${pontoEdit.id}`, { method: "PATCH", token, json: pontoEdit });
      } else {
        await apiFetch(`/api/satisfacao/cadastro/perguntas/${perguntaSelecionada.id}/pontos-avaliacao`, { method: "POST", token, json: pontoEdit });
      }
      setPontoEdit(null);
      apiFetch<PontoAvaliacao[]>(`/api/satisfacao/cadastro/perguntas/${perguntaSelecionada.id}/pontos-avaliacao`, { token }).then(setPontos);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao salvar ponto de avaliação"); }
  }

  async function desativarPonto(id: string) {
    try {
      await apiFetch(`/api/satisfacao/cadastro/pontos-avaliacao/${id}`, { method: "DELETE", token });
      if (perguntaSelecionada) apiFetch<PontoAvaliacao[]>(`/api/satisfacao/cadastro/perguntas/${perguntaSelecionada.id}/pontos-avaliacao`, { token }).then(setPontos);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro ao desativar"); }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Pesquisa de Satisfação — Cadastro</h1>

      {msg && <div className="text-sm bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded-lg px-4 py-2">{msg}</div>}

      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700">
        {SUBTABS.map((t) => (
          <button key={t.id} onClick={() => setSubtab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${subtab === t.id ? "border-[#00694E] text-[#00694E]" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {subtab === "clientes" && (
        <>
          <div className="flex justify-end">
            <button onClick={() => setClienteEdit({ empresa_nome: "", contato_nome: "", contato_email: "" })}
              className="bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold px-4 py-2 rounded-lg text-sm">Novo cliente</button>
          </div>
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900/50 text-left text-gray-500">
                <tr><th className="p-3">Empresa</th><th className="p-3">Contato</th><th className="p-3">E-mail</th><th className="p-3">Status</th><th className="p-3">Ações</th></tr>
              </thead>
              <tbody>
                {clientes.map((c) => (
                  <tr key={c.id} className="border-t border-gray-100 dark:border-gray-700">
                    <td className="p-3">{c.empresa_nome}</td>
                    <td className="p-3">{c.contato_nome}</td>
                    <td className="p-3 text-xs">{c.contato_email}</td>
                    <td className="p-3">{c.ativo ? <span className="text-green-600 text-xs">Ativo</span> : <span className="text-gray-400 text-xs">Inativo</span>}</td>
                    <td className="p-3 flex gap-2">
                      <button onClick={() => setClienteEdit(c)} className="text-xs text-[#00694E] hover:underline">Editar</button>
                      {c.ativo && <button onClick={() => desativarCliente(c.id)} className="text-xs text-red-500 hover:underline">Desativar</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}

      {subtab === "perguntas" && (
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <div className="flex justify-end mb-3">
              <button onClick={() => setPerguntaEdit({ texto: "", categoria: "" })}
                className="bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold px-4 py-2 rounded-lg text-sm">Nova pergunta</button>
            </div>
            <div className="space-y-2">
              {perguntas.map((p) => (
                <Card key={p.id} className={`p-4 cursor-pointer ${perguntaSelecionada?.id === p.id ? "border-[#00694E]" : ""}`} >
                  <div className="flex items-start justify-between gap-3">
                    <div onClick={() => setPerguntaSelecionada(p)} className="flex-1">
                      <p className={`text-sm font-medium ${p.ativa ? "text-gray-900 dark:text-gray-100" : "text-gray-400 line-through"}`}>{p.texto}</p>
                      <p className="text-xs text-gray-400 mt-1">Ordem {p.ordem} · {p.categoria || "sem categoria"}</p>
                    </div>
                    <div className="flex flex-col gap-1 items-end">
                      <button onClick={() => setPerguntaEdit(p)} className="text-xs text-[#00694E] hover:underline">Editar</button>
                      {p.ativa && <button onClick={() => desativarPergunta(p.id)} className="text-xs text-red-500 hover:underline">Desativar</button>}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>

          <div>
            <h3 className="font-bold text-gray-900 dark:text-gray-100 mb-3">
              Pontos de avaliação {perguntaSelecionada ? `— ${perguntaSelecionada.texto.slice(0, 40)}...` : ""}
            </h3>
            {!perguntaSelecionada && <p className="text-sm text-gray-400">Selecione uma pergunta à esquerda.</p>}
            {perguntaSelecionada && (
              <>
                <div className="flex justify-end mb-3">
                  <button onClick={() => setPontoEdit({ titulo: "", descricao: "" })}
                    className="bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold px-3 py-1.5 rounded-lg text-xs">Novo ponto</button>
                </div>
                <div className="space-y-2">
                  {pontos.map((p) => (
                    <Card key={p.id} className="p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={`text-sm font-medium ${p.ativo ? "text-gray-900 dark:text-gray-100" : "text-gray-400 line-through"}`}>{p.titulo}</p>
                          <p className="text-xs text-gray-500 mt-1">{p.descricao}</p>
                        </div>
                        <div className="flex flex-col gap-1 items-end">
                          <button onClick={() => setPontoEdit(p)} className="text-xs text-[#00694E] hover:underline">Editar</button>
                          {p.ativo && <button onClick={() => desativarPonto(p.id)} className="text-xs text-red-500 hover:underline">Desativar</button>}
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      <ModalWrapper open={!!clienteEdit} onClose={() => setClienteEdit(null)} title={clienteEdit?.id ? "Editar cliente" : "Novo cliente"}>
        {clienteEdit && (
          <div className="space-y-3">
            <input type="text" placeholder="Empresa" value={clienteEdit.empresa_nome || ""} onChange={(e) => setClienteEdit({ ...clienteEdit, empresa_nome: e.target.value })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <input type="text" placeholder="Nome do contato" value={clienteEdit.contato_nome || ""} onChange={(e) => setClienteEdit({ ...clienteEdit, contato_nome: e.target.value })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <input type="text" placeholder="Cargo (opcional)" value={clienteEdit.contato_cargo || ""} onChange={(e) => setClienteEdit({ ...clienteEdit, contato_cargo: e.target.value })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <input type="email" placeholder="E-mail" value={clienteEdit.contato_email || ""} onChange={(e) => setClienteEdit({ ...clienteEdit, contato_email: e.target.value })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <input type="text" placeholder="Telefone (opcional)" value={clienteEdit.contato_telefone || ""} onChange={(e) => setClienteEdit({ ...clienteEdit, contato_telefone: e.target.value })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <button onClick={salvarCliente} className="w-full bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold py-2 rounded-lg text-sm">Salvar</button>
          </div>
        )}
      </ModalWrapper>

      <ModalWrapper open={!!perguntaEdit} onClose={() => setPerguntaEdit(null)} title={perguntaEdit?.id ? "Editar pergunta" : "Nova pergunta"}>
        {perguntaEdit && (
          <div className="space-y-3">
            <textarea placeholder="Texto da pergunta" value={perguntaEdit.texto || ""} onChange={(e) => setPerguntaEdit({ ...perguntaEdit, texto: e.target.value })}
              rows={3} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <input type="text" placeholder="Categoria (opcional)" value={perguntaEdit.categoria || ""} onChange={(e) => setPerguntaEdit({ ...perguntaEdit, categoria: e.target.value })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <button onClick={salvarPergunta} className="w-full bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold py-2 rounded-lg text-sm">Salvar</button>
          </div>
        )}
      </ModalWrapper>

      <ModalWrapper open={!!pontoEdit} onClose={() => setPontoEdit(null)} title={pontoEdit?.id ? "Editar ponto de avaliação" : "Novo ponto de avaliação"}>
        {pontoEdit && (
          <div className="space-y-3">
            <input type="text" placeholder="Título" value={pontoEdit.titulo || ""} onChange={(e) => setPontoEdit({ ...pontoEdit, titulo: e.target.value })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <textarea placeholder="Descrição (o que verificar)" value={pontoEdit.descricao || ""} onChange={(e) => setPontoEdit({ ...pontoEdit, descricao: e.target.value })}
              rows={3} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
            <button onClick={salvarPonto} className="w-full bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold py-2 rounded-lg text-sm">Salvar</button>
          </div>
        )}
      </ModalWrapper>
    </div>
  );
}
