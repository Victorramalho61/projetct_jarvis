import type { CalculoDetalhado } from "../../types/rh";

type Props = {
  detalhamento: CalculoDetalhado;
  onClose: () => void;
};

const LINHAS: { campo: keyof CalculoDetalhado; label: string }[] = [
  { campo: "salario", label: "Salário" },
  { campo: "vale_transporte", label: "Vale transporte" },
  { campo: "vale_alimentacao", label: "Vale alimentação/refeição" },
  { campo: "provisao_13_ferias", label: "13º Salário + 1/3 férias" },
  { campo: "ferias", label: "Férias" },
  { campo: "inss", label: "INSS" },
  { campo: "fgts", label: "FGTS" },
  { campo: "fgts_multa", label: "FGTS Multa Rescisória" },
  { campo: "inss_13_ferias", label: "INSS sobre 13º e férias" },
  { campo: "seguro_vida", label: "Seguro de vida" },
  { campo: "plano_saude", label: "Plano de saúde" },
  { campo: "uniforme", label: "Uniforme completo" },
  { campo: "cracha_cordao", label: "Crachá e cordão" },
  { campo: "aso", label: "ASO" },
  { campo: "taxa_administrativa", label: "Taxa administrativa" },
];

const LINHAS_INFORMATIVAS: { campo: keyof CalculoDetalhado; label: string }[] = [
  { campo: "insalubridade_informativo", label: "Insalubridade" },
  { campo: "periculosidade_informativo", label: "Periculosidade" },
  { campo: "aparelhos_eletronicos_informativo", label: "Aparelhos eletrônicos" },
  { campo: "outros_creditos_informativo", label: "Outros créditos" },
];

function fmt(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function DetalhamentoCalculoModal({ detalhamento, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-xl bg-white dark:bg-gray-900 p-6 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">Detalhamento do custo de admissão</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none">&times;</button>
        </div>

        <table className="w-full text-sm">
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {LINHAS.map((l) => (
              <tr key={l.campo}>
                <td className="py-1.5 text-gray-600 dark:text-gray-300">{l.label}</td>
                <td className="py-1.5 text-right font-medium text-gray-900 dark:text-gray-100">{fmt(detalhamento[l.campo] as number)}</td>
              </tr>
            ))}
            <tr className="border-t-2 border-gray-300 dark:border-gray-700">
              <td className="py-2 font-bold text-gray-900 dark:text-gray-100">Custo Total</td>
              <td className="py-2 text-right font-bold text-emerald-600 dark:text-emerald-400">{fmt(detalhamento.custo_total)}</td>
            </tr>
          </tbody>
        </table>

        <div className="mt-4 rounded-lg bg-gray-50 dark:bg-gray-800/60 p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">Informativos (não somados ao total)</p>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {LINHAS_INFORMATIVAS.map((l) => (
                <tr key={l.campo}>
                  <td className="py-1 text-gray-500 dark:text-gray-400">{l.label}</td>
                  <td className="py-1 text-right text-gray-500 dark:text-gray-400">{fmt(detalhamento[l.campo] as number)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <button onClick={onClose} className="mt-4 w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          Fechar
        </button>
      </div>
    </div>
  );
}
