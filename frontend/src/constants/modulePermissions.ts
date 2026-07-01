export interface ModulePermission {
  id: string;    // chave usada em profiles.allowed_modules
  label: string; // rótulo exibido na Gestão de Acesso
  navId: string; // id correspondente em NAV_ITEMS (AppLayout)
}

// Fonte única dos módulos com controle de acesso — usada por AppLayout
// (filtro de navegação) e AccessManagementPage (checklist de permissões).
// Adicionar um módulo aqui é suficiente para ele aparecer nos dois lugares.
export const MODULE_PERMISSIONS: ModulePermission[] = [
  { id: "desempenho",    label: "Gestão de Desempenho",  navId: "desempenho" },
  { id: "moneypenny",    label: "Moneypenny",            navId: "moneypenny" },
  { id: "monitoramento", label: "Monitoramento",         navId: "monitoring" },
  { id: "freshservice",  label: "Freshservice",          navId: "freshservice" },
  { id: "agentes",       label: "Agentes",               navId: "agents" },
  { id: "gastos_ti",     label: "Gastos TI",             navId: "expenses" },
  { id: "fiscal",        label: "Validação NFe/NFSe",    navId: "fiscal" },
  { id: "governanca",    label: "Governança",            navId: "governance" },
  { id: "payfly",        label: "PayFly",                navId: "payfly" },
  { id: "hermes",        label: "Hermes Agent",          navId: "hermes" },
  { id: "cartoes",       label: "Cofre de Cartões",      navId: "cartoes" },
  { id: "financeiro",    label: "Financeiro",            navId: "financeiro" },
  { id: "experiencia",   label: "Aval. de Experiência",  navId: "experiencia" },
];
