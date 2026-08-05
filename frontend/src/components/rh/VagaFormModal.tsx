import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, ApiError } from "../../lib/api";
import type { RhLookups } from "../../hooks/useRhLookups";
import type { Vaga } from "../../types/rh";

const FIELD_CLASS =
  "w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";
const LABEL_CLASS = "mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300";

const CARGA_HORARIA_OPCOES = ["180h", "220h", "12x36", "Outros"];

type Props = {
  vagaId: string;
  lookups: RhLookups;
  token: string | null;
  onClose: () => void;
  onSaved: () => void;
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className={LABEL_CLASS}>{label}</label>{children}</div>;
}

function LookupSelect({
  value, onChange, options, placeholder = "— selecione —",
}: { value: string | null; onChange: (v: string) => void; options: { id: string; nome?: string; sigla?: string }[]; placeholder?: string }) {
  return (
    <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} className={FIELD_CLASS}>
      <option value="">{placeholder}</option>
      {options.map((o) => <option key={o.id} value={o.id}>{o.nome ?? o.sigla}</option>)}
    </select>
  );
}

export default function VagaFormModal({ vagaId, lookups, token, onClose, onSaved }: Props) {
  const navigate = useNavigate();
  const [vaga, setVaga] = useState<Vaga | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    apiFetch<Vaga>(`/api/rh/vagas/${vagaId}`, { token })
      .then(setVaga)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erro ao carregar vaga."))
      .finally(() => setLoading(false));
  }, [vagaId, token]);

  async function patch(fields: Record<string, unknown>) {
    setVaga((prev) => (prev ? { ...prev, ...fields } as Vaga : prev));
    setSaving(true);
    setError(null);
    try {
      const atualizado = await apiFetch<Vaga>(`/api/rh/vagas/${vagaId}`, { method: "PATCH", json: fields, token });
      setVaga(atualizado);
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    try {
      await apiFetch(`/api/rh/vagas/${vagaId}`, { method: "DELETE", token });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao excluir.");
    }
  }

  if (loading || !vaga) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="rounded-xl bg-white dark:bg-gray-900 px-6 py-4 text-sm text-gray-500">Carregando processo...</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4">
      <div className="flex w-full max-w-3xl flex-col rounded-t-xl bg-white dark:bg-gray-900 shadow-xl sm:rounded-xl max-h-[94vh]">

        <div className="flex shrink-0 items-center justify-between border-b border-gray-100 dark:border-gray-800 px-4 py-4 sm:px-6">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-gray-100">
              Processo {vaga.numero_requisicao ?? "(gerando...)"}
            </h2>
            <p className="text-xs text-gray-400">{saving ? "Salvando..." : "Alterações salvas automaticamente"}</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/rh/vagas/${vaga.id}/imprimir`)}
              className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
            >
              Imprimir formulário
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none">&times;</button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6 space-y-6">
          {error && (
            <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-700 dark:text-red-300">{error}</div>
          )}

          <section>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Dados gerais da vaga</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Empresa">
                <LookupSelect value={vaga.empresa_id} onChange={(v) => patch({ empresa_id: v })} options={lookups.empresas} />
              </Field>
              <Field label="Data de recebimento">
                <input type="date" value={vaga.data_recebimento ?? ""} onChange={(e) => patch({ data_recebimento: e.target.value })} className={FIELD_CLASS} />
              </Field>
              <Field label="Centro de custo">
                <input value={vaga.centro_custo ?? ""} onChange={(e) => setVaga({ ...vaga, centro_custo: e.target.value })} onBlur={(e) => patch({ centro_custo: e.target.value })} className={FIELD_CLASS} />
              </Field>
              <Field label="Hierarquia">
                <LookupSelect value={vaga.hierarquia_id} onChange={(v) => patch({ hierarquia_id: v })} options={lookups.hierarquias} />
              </Field>
              <Field label="Alocação real">
                <LookupSelect value={vaga.alocacao_id} onChange={(v) => patch({ alocacao_id: v })} options={lookups.alocacoes} />
              </Field>
              <Field label="UF">
                <LookupSelect value={vaga.uf ? lookups.ufs.find((u) => u.sigla === vaga.uf)?.id ?? null : null}
                  onChange={(id) => patch({ uf: lookups.ufs.find((u) => u.id === id)?.sigla ?? "" })}
                  options={lookups.ufs} />
              </Field>
              <Field label="Requisitante (solicitante)">
                <LookupSelect value={vaga.requisitante_id} onChange={(v) => patch({ requisitante_id: v })} options={lookups.requisitantes} />
              </Field>
              <Field label="Data de aprovação da diretoria">
                <input type="date" value={vaga.data_aprovacao_diretoria ?? ""} onChange={(e) => patch({ data_aprovacao_diretoria: e.target.value })} className={FIELD_CLASS} />
              </Field>
            </div>
          </section>

          <section>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Cargo e condições</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Cargo (o nível é preenchido automaticamente)">
                <LookupSelect value={vaga.cargo_id} onChange={(v) => patch({ cargo_id: v })} options={lookups.cargos} />
              </Field>
              <Field label="Nível">
                <LookupSelect value={vaga.nivel_id} onChange={(v) => patch({ nivel_id: v })} options={lookups.niveis} />
              </Field>
              <Field label="Tipo de contrato">
                <LookupSelect value={vaga.tipo_contrato_id} onChange={(v) => patch({ tipo_contrato_id: v })} options={lookups["tipos-contrato"]} />
              </Field>
              <Field label="Modalidade">
                <LookupSelect value={vaga.modalidade_id} onChange={(v) => patch({ modalidade_id: v })} options={lookups.modalidades} />
              </Field>
              <Field label="Carga horária">
                <select value={vaga.carga_horaria ?? ""} onChange={(e) => patch({ carga_horaria: e.target.value })} className={FIELD_CLASS}>
                  <option value="">— selecione —</option>
                  {CARGA_HORARIA_OPCOES.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              </Field>
              {vaga.carga_horaria === "Outros" && (
                <Field label="Especifique a carga horária">
                  <input value={vaga.carga_horaria_outros ?? ""} onChange={(e) => setVaga({ ...vaga, carga_horaria_outros: e.target.value })} onBlur={(e) => patch({ carga_horaria_outros: e.target.value })} className={FIELD_CLASS} />
                </Field>
              )}
              <Field label="Horário de trabalho">
                <input value={vaga.horario_trabalho ?? ""} placeholder="Ex: 8h às 18h" onChange={(e) => setVaga({ ...vaga, horario_trabalho: e.target.value })} onBlur={(e) => patch({ horario_trabalho: e.target.value })} className={FIELD_CLASS} />
              </Field>
              <Field label="Salário">
                <input type="number" step="0.01" value={vaga.salario ?? ""} onChange={(e) => setVaga({ ...vaga, salario: Number(e.target.value) })} onBlur={(e) => patch({ salario: Number(e.target.value) })} className={FIELD_CLASS} />
              </Field>
            </div>
          </section>

          <section>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Justificativa</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Tipo de vaga">
                <LookupSelect value={vaga.tipo_vaga_id} onChange={(v) => patch({ tipo_vaga_id: v })} options={lookups["tipos-vaga"]} />
              </Field>
              <Field label="Justificativa (ex: nome de quem está sendo substituído)">
                <input value={vaga.justificativa ?? ""} onChange={(e) => setVaga({ ...vaga, justificativa: e.target.value })} onBlur={(e) => patch({ justificativa: e.target.value })} className={FIELD_CLASS} />
              </Field>
            </div>
          </section>

          <section>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Processo e acompanhamento</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Etapa atual (a seção e o status são atualizados automaticamente)">
                <LookupSelect value={vaga.etapa_atual_id} onChange={(v) => patch({ etapa_atual_id: v })} options={lookups.etapas} />
              </Field>
              <Field label="Seção responsável">
                <LookupSelect value={vaga.secao_id} onChange={(v) => patch({ secao_id: v })} options={lookups.secoes} />
              </Field>
              <Field label="Status da vaga">
                <LookupSelect value={vaga.status_id} onChange={(v) => patch({ status_id: v })} options={lookups.status} />
              </Field>
              <Field label="Analista responsável (R&S)">
                <LookupSelect value={vaga.responsavel_id} onChange={(v) => patch({ responsavel_id: v })} options={lookups.analistas} />
              </Field>
              <Field label="SLA alvo (dias)">
                <input type="number" value={vaga.sla_alvo_dias ?? ""} onChange={(e) => setVaga({ ...vaga, sla_alvo_dias: Number(e.target.value) })} onBlur={(e) => patch({ sla_alvo_dias: Number(e.target.value) })} className={FIELD_CLASS} />
              </Field>
            </div>
          </section>

          <section>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Admissão</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Candidato(a) aprovado(a)">
                <input value={vaga.candidato ?? ""} onChange={(e) => setVaga({ ...vaga, candidato: e.target.value })} onBlur={(e) => patch({ candidato: e.target.value })} className={FIELD_CLASS} />
              </Field>
              <Field label="Data de admissão / início">
                <input type="date" value={vaga.data_admissao ?? ""} onChange={(e) => patch({ data_admissao: e.target.value })} className={FIELD_CLASS} />
              </Field>
            </div>
          </section>
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-gray-100 dark:border-gray-800 px-4 py-4 sm:px-6">
          <div>
            {!confirmDelete && (
              <button onClick={() => setConfirmDelete(true)} className="text-sm text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300">
                Excluir processo
              </button>
            )}
            {confirmDelete && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-red-600 dark:text-red-400">Confirmar exclusão?</span>
                <button onClick={handleDelete} className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700">Excluir</button>
                <button onClick={() => setConfirmDelete(false)} className="text-sm text-gray-500 dark:text-gray-400">Cancelar</button>
              </div>
            )}
          </div>
          <button onClick={onClose} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
