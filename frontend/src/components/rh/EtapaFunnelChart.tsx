import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Props = {
  data: { etapa: string; ordem: number; total: number }[];
};

const CORES = ["#3b82f6", "#3b82f6", "#3b82f6", "#3b82f6", "#3b82f6", "#3b82f6", "#3b82f6",
  "#3b82f6", "#3b82f6", "#3b82f6", "#f59e0b", "#f59e0b", "#f59e0b", "#f59e0b", "#22c55e", "#ef4444"];

export default function EtapaFunnelChart({ data }: Props) {
  if (data.every((d) => d.total === 0)) {
    return <p className="text-sm text-gray-400 py-8 text-center">Nenhuma vaga com etapa registrada no período.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={420}>
      <BarChart data={data} layout="vertical" margin={{ left: 24, right: 16 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" allowDecimals={false} />
        <YAxis type="category" dataKey="etapa" width={200} tick={{ fontSize: 11 }} />
        <Tooltip />
        <Bar dataKey="total" radius={[0, 4, 4, 0]}>
          {data.map((d, i) => <Cell key={d.etapa} fill={CORES[i % CORES.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
