type Props = {
  titulo: string;
  quantidade: number;
  variante: "estourado" | "estourando";
  onClick: () => void;
};

export default function AlertaSlaTile({ titulo, quantidade, variante, onClick }: Props) {
  const temAlerta = quantidade > 0;

  const estilos = temAlerta
    ? variante === "estourado"
      ? "border-red-500 bg-red-50 dark:bg-red-950/40 dark:border-red-700 animate-pulse-slow"
      : "border-amber-500 bg-amber-50 dark:bg-amber-950/40 dark:border-amber-700 animate-pulse-slow"
    : "border-green-300 bg-green-50 dark:bg-green-950/30 dark:border-green-800";

  const corTexto = temAlerta
    ? variante === "estourado"
      ? "text-red-700 dark:text-red-300"
      : "text-amber-700 dark:text-amber-300"
    : "text-green-700 dark:text-green-300";

  const icone = temAlerta ? (variante === "estourado" ? "⚠" : "⏳") : "✓";

  return (
    <button
      onClick={onClick}
      className={`group w-full rounded-xl border-2 p-4 text-left transition-transform hover:-translate-y-0.5 ${estilos}`}
    >
      <style>{`
        @keyframes pulse-slow { 0%, 100% { opacity: 1; } 50% { opacity: 0.75; } }
        .animate-pulse-slow { animation: pulse-slow 2.5s ease-in-out infinite; }
      `}</style>
      <div className="flex items-center justify-between">
        <span className={`text-2xl ${corTexto}`}>{icone}</span>
        <span className={`text-3xl font-bold ${corTexto}`}>{quantidade}</span>
      </div>
      <p className={`mt-1 text-sm font-bold ${corTexto}`}>{titulo}</p>
      <p className={`text-xs ${corTexto} opacity-80`}>
        {temAlerta ? "Clique para ver detalhes →" : "Tudo dentro do prazo"}
      </p>
    </button>
  );
}
