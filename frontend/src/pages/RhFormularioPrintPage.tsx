import { useEffect, useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import type { Vaga } from "../types/rh";

const CARGA_HORARIA_OPCOES = ["180h", "220h", "12x36", "Outros"];
const MODALIDADE_OPCOES = ["HORISTA", "INTERMITENTE", "DETERMINADO", "INDETERMINADO"];

function Check({ marcado }: { marcado: boolean }) {
  return <span className="font-mono">( {marcado ? "x" : " "} )</span>;
}

function fmtData(iso: string | null): string {
  if (!iso) return "____/____/____";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function fmtMoeda(v: number | null): string {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function RhFormularioPrintPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [vaga, setVaga] = useState<Vaga | null>(null);

  useEffect(() => {
    if (id) apiFetch<Vaga>(`/api/rh/vagas/${id}`, { token }).then(setVaga);
  }, [id, token]);

  if (!vaga) {
    return <div className="p-8 text-center text-gray-500">Carregando formulário...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950 py-8 print:bg-white print:py-0">
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { background: white; }
        }
      `}</style>

      <div className="mx-auto max-w-3xl bg-white text-black shadow-lg print:shadow-none" style={{ fontFamily: "Arial, sans-serif" }}>
        <div className="flex justify-end gap-2 p-4 no-print">
          <button onClick={() => window.print()} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            Imprimir
          </button>
        </div>

        <div className="border border-black text-[12px] leading-tight">
          {/* Cabeçalho */}
          <div className="flex items-center justify-between border-b border-black px-4 py-3">
            <div className="text-2xl font-bold tracking-tight" style={{ color: "#0f766e" }}>
              GRUPO<br /><span className="text-xl">VOETUR</span>
            </div>
            <div className="text-center flex-1">
              <p className="text-base font-bold">REQUISIÇÃO DE PESSOAL</p>
            </div>
            <div className="text-right text-[10px] leading-tight">
              <p>Versão 08</p>
              <p>Anexo 01</p>
              <p>VPA.RH.PGP.01</p>
              <p>Data: 16/06/2026</p>
            </div>
          </div>

          <Row cols={[
            { label: "Solicitante", value: vaga.requisitante ?? "—" },
            { label: "Data", value: fmtData(vaga.data_recebimento) },
            { label: "Nº Requisição", value: vaga.numero_requisicao ?? "—" },
          ]} />
          <Row cols={[
            { label: "Centro de Custo", value: vaga.centro_custo ?? "—" },
            { label: "Empresa", value: vaga.empresa ?? "—", span: 2 },
          ]} />
          <Row cols={[
            { label: "Hierarquia", value: vaga.hierarquia ?? "—" },
            { label: "Alocação Real", value: vaga.alocacao ?? "—", span: 2 },
          ]} />

          <SectionTitle>DADOS GERAIS DA VAGA (preenchimento obrigatório)</SectionTitle>
          <div className="border-b border-black px-4 py-1"><strong>Cargo:</strong> {vaga.cargo ?? "—"}</div>
          <div className="border-b border-black px-4 py-1 flex flex-wrap gap-4">
            <strong>Carga horária:</strong>
            {CARGA_HORARIA_OPCOES.map((o) => (
              <span key={o}>{o} <Check marcado={vaga.carga_horaria === o} /></span>
            ))}
            {vaga.carga_horaria === "Outros" && vaga.carga_horaria_outros && (
              <span>({vaga.carga_horaria_outros})</span>
            )}
            <span className="ml-auto"><strong>Horário:</strong> {vaga.horario_trabalho ?? "—"}</span>
          </div>
          <div className="border-b border-black px-4 py-1 flex flex-wrap gap-4">
            <strong>Modalidade:</strong>
            {MODALIDADE_OPCOES.map((o) => (
              <span key={o}>{o.charAt(0) + o.slice(1).toLowerCase()} <Check marcado={vaga.modalidade === o} /></span>
            ))}
          </div>
          <div className="border-b border-black px-4 py-1"><strong>Salário:</strong> {fmtMoeda(vaga.salario)}</div>

          <SectionTitle>JUSTIFICATIVA (preenchimento obrigatório)</SectionTitle>
          <div className="border-b border-black px-4 py-1">
            <Check marcado={vaga.tipo_vaga === "AUMENTO DE QUADRO"} /> Aumento de quadro
          </div>
          <div className="border-b border-black px-4 py-1">
            <Check marcado={vaga.tipo_vaga === "NOVA POSIÇÃO"} /> Nova posição
          </div>
          <div className="border-b border-black px-4 py-1">
            <Check marcado={vaga.tipo_vaga === "SUBSTITUIÇÃO"} /> Substituição
            {vaga.tipo_vaga === "SUBSTITUIÇÃO" && vaga.justificativa && `: ${vaga.justificativa}`}
          </div>

          <SectionTitle>CUSTOS DA ADMISSÃO (Documento emitido pelo Departamento Pessoal, anexo a este documento).</SectionTitle>
          <Row cols={[
            { label: "Candidato(a) Aprovado(a)", value: vaga.candidato ?? "—", span: 2 },
            { label: "Data de Início", value: fmtData(vaga.data_admissao) },
          ]} />

          <SectionTitle>AUTORIZAÇÕES DEVIDAS (preenchimento obrigatório)</SectionTitle>
          <div className="grid grid-cols-3 divide-x divide-black border-b border-black">
            {["Solicitante", "Recursos Humanos", "Departamento Pessoal"].map((label) => (
              <div key={label} className="px-4 py-6 text-center">
                <p className="font-semibold">{label}</p>
                <div className="mt-8 border-t border-black pt-1">Assinatura/Carimbo</div>
                <p className="mt-2">Data: _____/_____/_____</p>
              </div>
            ))}
          </div>

          <SectionTitle>AUTORIZAÇÃO DIRETORIA (preenchimento obrigatório)</SectionTitle>
          <div className="px-4 py-10 text-center">
            <p>Local,________________, _____ de ________________ de ________.</p>
            <div className="mx-auto mt-10 w-2/3 border-t border-black pt-1">Assinatura/Carimbo</div>
          </div>

          <div className="flex items-center justify-between px-4 py-2 text-[10px]">
            <span>Tempo de retenção: 5 anos</span>
            <span>Anexo 01 v08</span>
            <span>Página 1 de 1</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <div className="border-b border-t border-black bg-gray-200 px-4 py-1 text-center text-[11px] font-bold">
      {children}
    </div>
  );
}

function Row({ cols }: { cols: { label: string; value: string; span?: number }[] }) {
  return (
    <div className="grid border-b border-black" style={{ gridTemplateColumns: cols.map((c) => `${c.span ?? 1}fr`).join(" ") }}>
      {cols.map((c, i) => (
        <div key={i} className={`px-4 py-1 ${i > 0 ? "border-l border-black" : ""}`}>
          <strong>{c.label}:</strong> {c.value}
        </div>
      ))}
    </div>
  );
}
