import { useEffect } from "react";

interface Props {
  sql: string;
  onClose: () => void;
}

export default function SqlDebugModal({ sql, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const copy = () => navigator.clipboard.writeText(sql).catch(() => {});

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 rounded-xl w-full max-w-4xl max-h-[80vh] flex flex-col shadow-2xl border border-gray-700"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700 flex-none">
          <span className="text-xs font-mono text-green-400 font-semibold tracking-widest uppercase">SQL Debug</span>
          <div className="flex items-center gap-2">
            <button
              onClick={copy}
              className="text-xs px-3 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 font-mono"
            >
              Copiar
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-white text-lg leading-none px-1">✕</button>
          </div>
        </div>
        <pre className="flex-1 overflow-auto p-4 text-green-300 font-mono text-xs leading-relaxed whitespace-pre-wrap break-words">
          {sql}
        </pre>
      </div>
    </div>
  );
}
