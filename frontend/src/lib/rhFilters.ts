import type { VagasFiltros } from "../types/rh";

export function filtrosToQueryString(filtros: VagasFiltros, extra?: Record<string, string | number>): string {
  const params = new URLSearchParams();
  if (filtros.q) params.set("q", filtros.q);
  if (filtros.data_inicio) params.set("data_inicio", filtros.data_inicio);
  if (filtros.data_fim) params.set("data_fim", filtros.data_fim);
  if (filtros.empresa_id) params.set("empresa_id", filtros.empresa_id);
  if (filtros.tipo_vaga_id) params.set("tipo_vaga_id", filtros.tipo_vaga_id);
  if (filtros.tipo_contrato_id) params.set("tipo_contrato_id", filtros.tipo_contrato_id);
  if (filtros.nivel_id) params.set("nivel_id", filtros.nivel_id);
  if (filtros.hierarquia_id) params.set("hierarquia_id", filtros.hierarquia_id);
  if (filtros.etapa_atual_id) params.set("etapa_atual_id", filtros.etapa_atual_id);
  if (filtros.secao_id) params.set("secao_id", filtros.secao_id);
  if (filtros.responsavel_id) params.set("responsavel_id", filtros.responsavel_id);
  if (filtros.requisitante_id) params.set("requisitante_id", filtros.requisitante_id);
  if (filtros.cargo_id) params.set("cargo_id", filtros.cargo_id);
  if (filtros.modalidade_id) params.set("modalidade_id", filtros.modalidade_id);
  (filtros.status_id ?? []).forEach((id) => params.append("status_id", id));
  (filtros.ano ?? []).forEach((a) => params.append("ano", String(a)));
  if (extra) {
    Object.entries(extra).forEach(([k, v]) => params.set(k, String(v)));
  }
  return params.toString();
}
