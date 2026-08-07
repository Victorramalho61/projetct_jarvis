import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  onClick: () => void;
};

export default function ClickableTileWrapper({ children, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="group block w-full rounded-xl text-left transition-transform hover:-translate-y-0.5 focus:outline-none"
    >
      <div className="rounded-xl ring-0 ring-blue-400 transition-shadow group-hover:ring-2">
        {children}
      </div>
      <p className="mt-1 text-center text-[10px] text-gray-400 opacity-0 transition-opacity group-hover:opacity-100">
        Clique para detalhar →
      </p>
    </button>
  );
}
