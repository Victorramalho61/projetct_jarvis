import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { EmpresaBenner } from "../../types/financeiro";

interface Props {
  onBuscar: (filtros: FiltroValues) => void;
  loading?: boolean;
  mostrarFilial?: boolean;
  mostrarConta?: boolean;
  mostrarNatureza?: boolean;
  semPeriodo?: boolean;
  dataUnica?: boolean;
}

export interface FiltroValues {
  empresa: string;
  filial: string;
  conta: string;
  natureza: "cliente" | "fornecedor";
  dataInicio: string;
  dataFim: string;
}

function hoje() {
  return new Date().toISOString().slice(0, 10);
}

function diasAtras(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function FiltroFinanceiro({
  onBuscar, loading, mostrarFilial, mostrarConta, mostrarNatureza, semPeriodo, dataUnica,
}: Props) {
  const { token } = useAuth();
  const [empresas, setEmpresas] = useState<EmpresaBenner[]>([]);
  const [empresa, setEmpresa] = useState("");
  const [filial, setFilial] = useState("");
  const [conta, setConta] = useState("");
  const [natureza, setNatureza] = useState<"cliente" | "fornecedor">("cliente");
  const [dataInicio, setDataInicio] = useState(diasAtras(7));
  const [dataFim, setDataFim] = useState(hoje());
  const [erroData, setErroData] = useState("");

  useEffect(() => {
    apiFetch<EmpresaBenner[]>("/api/financeiro/empresas", { token })
      .then(setEmpresas)
      .catch(() => {});
  }, [token]);

  function validarESubmit() {
    if (!semPeriodo && !dataUnica) {
      const ini = new Date(dataInicio);
      const fim = new Date(dataFim);
      const diff = Math.ceil((fim.getTime() - ini.getTime()) / 86400000);
      if (diff < 0) { setErroData("Data fim menor que data início."); return; }
      if (diff > 31) { setErroData("Período máximo de 31 dias."); return; }
      setErroData("");
    }
    onBuscar({ empresa, filial, conta, natureza, dataInicio, dataFim });
  }

  return (
    <div className="flex flex-wrap items-end gap-3 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Empresa</label>
        <select
          value={empresa}
          onChange={e => setEmpresa(e.target.value)}
          className="h-9 px-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm text-gray-800 dark:text-gray-100 min-w-[200px]"
        >
          <option value="">Todas</option>
          {empresas.map(e => (
            <option key={e.handle} value={e.handle}>{e.nome}</option>
          ))}
        </select>
      </div>

      {mostrarFilial && (
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Filial</label>
          <input
            value={filial}
            onChange={e => setFilial(e.target.value)}
            placeholder="Código filial"
            className="h-9 px-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm text-gray-800 dark:text-gray-100 w-32"
          />
        </div>
      )}

      {mostrarConta && (
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Conta</label>
          <input
            value={conta}
            onChange={e => setConta(e.target.value)}
            placeholder="Nº conta"
            className="h-9 px-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm text-gray-800 dark:text-gray-100 w-32"
          />
        </div>
      )}

      {mostrarNatureza && (
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Natureza</label>
          <select
            value={natureza}
            onChange={e => setNatureza(e.target.value as "cliente" | "fornecedor")}
            className="h-9 px-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm text-gray-800 dark:text-gray-100"
          >
            <option value="cliente">Clientes</option>
            <option value="fornecedor">Fornecedores</option>
          </select>
        </div>
      )}

      {dataUnica && (
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Data de referência</label>
          <input
            type="date"
            value={dataInicio}
            onChange={e => setDataInicio(e.target.value)}
            className="h-9 px-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm text-gray-800 dark:text-gray-100"
          />
        </div>
      )}

      {!semPeriodo && !dataUnica && (
        <>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Data início</label>
            <input
              type="date"
              value={dataInicio}
              onChange={e => setDataInicio(e.target.value)}
              className="h-9 px-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm text-gray-800 dark:text-gray-100"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Data fim</label>
            <input
              type="date"
              value={dataFim}
              onChange={e => setDataFim(e.target.value)}
              className="h-9 px-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm text-gray-800 dark:text-gray-100"
            />
          </div>
        </>
      )}

      <div className="flex flex-col gap-1">
        {erroData && <p className="text-xs text-red-500">{erroData}</p>}
        <button
          onClick={validarESubmit}
          disabled={loading}
          className="h-9 px-4 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium disabled:opacity-50"
        >
          {loading ? "Carregando..." : "Buscar"}
        </button>
      </div>
    </div>
  );
}
