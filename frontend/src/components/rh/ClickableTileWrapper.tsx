import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  onClick: () => void;
  hintSempreVisivel?: boolean;
};

export default function ClickableTileWrapper({ children, onClick, hintSempreVisivel = false }: Props) {
  return (
    <button
      onClick={onClick}
      className="group block w-full rounded-xl text-left transition-transform hover:-translate-y-0.5 focus:outline-none"
    >
      <div className="rounded-xl ring-0 ring-blue-400 transition-shadow group-hover:ring-2">
        {children}
      </div>
      <p
        className={`mt-1 text-center text-[10px] text-gray-400 transition-opacity group-hover:opacity-100 ${
          hintSempreVisivel ? "opacity-100" : "opacity-0"
        }`}
      >
        Clique para detalhar →
      </p>
    </button>
  );
}
