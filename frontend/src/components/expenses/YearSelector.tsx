interface YearSelectorProps {
  value: number
  onChange: (year: number) => void
  years?: number[]
}

export default function YearSelector({ value, onChange, years = [2025, 2026] }: YearSelectorProps) {
  return (
    <div className="inline-flex rounded-lg border border-gray-700 overflow-hidden">
      {years.map((year) => (
        <button
          key={year}
          type="button"
          onClick={() => onChange(year)}
          className={`px-4 py-1.5 text-sm font-semibold transition-colors ${
            value === year
              ? 'bg-blue-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
          }`}
        >
          {year}
        </button>
      ))}
    </div>
  )
}
