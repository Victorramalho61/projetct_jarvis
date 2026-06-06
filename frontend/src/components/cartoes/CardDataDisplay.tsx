import { useEffect, useRef, useState } from "react";

interface CardDataDisplayProps {
  numero: string;
  cvv: string;
  expiracao: string;
  titular: string;
  bandeira: string;
  onExpired: () => void;
}

const BANDEIRA_COLORS: Record<string, string> = {
  VISA: "from-blue-800 to-blue-600",
  MASTER: "from-red-700 to-orange-500",
  ELO: "from-yellow-600 to-yellow-400",
  AMEX: "from-green-700 to-green-500",
  HIPERCARD: "from-red-800 to-red-600",
};

export default function CardDataDisplay({ numero, cvv, expiracao, titular, bandeira, onExpired }: CardDataDisplayProps) {
  const TOTAL = 60;
  const [remaining, setRemaining] = useState(TOTAL);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(intervalRef.current!);
          onExpired();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(intervalRef.current!);
  }, [onExpired]);

  const gradient = BANDEIRA_COLORS[bandeira.toUpperCase()] ?? "from-gray-700 to-gray-500";
  const pct = (remaining / TOTAL) * 100;
  const circumference = 2 * Math.PI * 22;
  const dash = (pct / 100) * circumference;

  return (
    <div className="space-y-4">
      {/* Cartão visual */}
      <div className={`relative rounded-2xl bg-gradient-to-br ${gradient} p-5 text-white shadow-lg select-none`}>
        {/* Chip */}
        <div className="mb-4 h-7 w-10 rounded-md bg-yellow-300/80" />

        {/* Número */}
        <div className="mb-4 font-mono text-xl tracking-widest">{numero}</div>

        <div className="flex items-end justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-white/70">Titular</p>
            <p className="font-semibold tracking-wide">{titular}</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] uppercase tracking-widest text-white/70">Validade</p>
            <p className="font-semibold">{expiracao}</p>
          </div>
        </div>

        <div className="absolute top-4 right-5 text-xs font-bold tracking-widest opacity-90">{bandeira}</div>
      </div>

      {/* CVV */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-4 py-3 flex items-center justify-between">
        <span className="text-sm text-gray-500 dark:text-gray-400">CVV</span>
        <span className="font-mono text-lg font-bold text-gray-900 dark:text-gray-100 tracking-widest">{cvv}</span>
      </div>

      {/* Countdown */}
      <div className="flex items-center justify-center gap-3 pt-1">
        <div className="relative h-12 w-12">
          <svg className="absolute inset-0 -rotate-90" viewBox="0 0 48 48">
            <circle cx="24" cy="24" r="22" fill="none" stroke="currentColor" strokeWidth="3"
              className="text-gray-200 dark:text-gray-700" />
            <circle cx="24" cy="24" r="22" fill="none" stroke="currentColor" strokeWidth="3"
              strokeDasharray={`${dash} ${circumference}`}
              className={remaining > 20 ? "text-emerald-500" : remaining > 10 ? "text-amber-500" : "text-red-500"}
              strokeLinecap="round"
              style={{ transition: "stroke-dasharray 1s linear" }}
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center font-mono text-sm font-bold text-gray-700 dark:text-gray-200">
            {remaining}
          </span>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Dados serão apagados automaticamente em <span className="font-semibold">{remaining}s</span>
        </p>
      </div>

      <p className="text-center text-xs text-gray-400 dark:text-gray-600">
        Não copie ou fotografe estes dados. Seu acesso foi registrado.
      </p>
    </div>
  );
}
