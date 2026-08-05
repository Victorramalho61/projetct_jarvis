import { useEffect, useRef, useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";
import type { ImportResultado, UploadInfo } from "../../types/rh";

type Props = {
  token: string | null;
  onImported: () => void;
};

export default function UploadPlanilhaPanel({ token, onImported }: Props) {
  const [ultimo, setUltimo] = useState<UploadInfo | null>(null);
  const [uploading, setUploading] = useState(false);
  const [resultado, setResultado] = useState<ImportResultado | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function carregarUltimo() {
    apiFetch<UploadInfo | null>("/api/rh/uploads/ultimo", { token }).then(setUltimo).catch(() => {});
  }

  useEffect(() => { carregarUltimo(); }, [token]);

  async function handleTemplate() {
    const res = await fetch("/api/rh/vagas/template", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "modelo_controle_de_vagas.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleUpload(file: File) {
    setUploading(true);
    setError(null);
    setResultado(null);
    try {
      const fd = new FormData();
      fd.append("arquivo", file);
      const resp = await fetch("/api/rh/vagas/import", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const json = await resp.json();
      if (!resp.ok) throw new Error(json.detail ?? "Erro ao importar planilha.");
      setResultado(json as ImportResultado);
      carregarUltimo();
      onImported();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Erro ao importar planilha.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Upload da planilha de vagas</h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Envie a planilha (.xlsx) para atualizar em massa status, etapas e datas de todas as vagas.
          Vagas já existentes (mesmo nº de requisição) são <strong>atualizadas</strong>; vagas novas são inseridas.
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            onClick={handleTemplate}
            className="rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Baixar modelo (.xlsx)
          </button>

          <label className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 cursor-pointer">
            {uploading ? "Enviando..." : "Selecionar planilha e enviar"}
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx"
              className="hidden"
              disabled={uploading}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); }}
            />
          </label>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-700 dark:text-red-300">{error}</div>
        )}

        {resultado && (
          <div className="mt-4 rounded-lg border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 px-4 py-3 text-sm text-green-800 dark:text-green-300">
            <p className="font-semibold">Importação concluída.</p>
            <p>{resultado.linhas_processadas} linha(s) processada(s) — {resultado.linhas_inseridas} inserida(s), {resultado.linhas_atualizadas} atualizada(s), {resultado.linhas_com_erro} com erro.</p>
            {resultado.erros.length > 0 && (
              <ul className="mt-2 max-h-40 overflow-y-auto list-disc pl-5 text-xs text-amber-700 dark:text-amber-400">
                {resultado.erros.map((e, i) => (
                  <li key={i}>Linha {e.linha ?? "?"}: {e.motivo}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Último upload</h3>
        {!ultimo ? (
          <p className="mt-2 text-sm text-gray-400">Nenhum upload registrado ainda.</p>
        ) : (
          <div className="mt-2 text-sm text-gray-600 dark:text-gray-300 space-y-1">
            <p><strong>{ultimo.usuario_nome}</strong> em {new Date(ultimo.criado_em).toLocaleString("pt-BR")}</p>
            <p className="text-gray-500 dark:text-gray-400">{ultimo.arquivo_nome}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {ultimo.linhas_processadas} processada(s) · {ultimo.linhas_inseridas} inserida(s) · {ultimo.linhas_atualizadas} atualizada(s) · {ultimo.linhas_com_erro} com erro
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
