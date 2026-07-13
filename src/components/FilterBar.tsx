import { strings } from '../copy/strings'
import type { FilterValue } from '../lib/taskUtils'

const FILTERS: { value: FilterValue; label: string }[] = [
  { value: 'all', label: strings.tasks.filterAll },
  { value: 'active', label: strings.tasks.filterActive },
  { value: 'completed', label: strings.tasks.filterCompleted },
]

export function FilterBar({ value, onChange }: { value: FilterValue; onChange: (v: FilterValue) => void }) {
  return (
    <div className="flex gap-2">
      {FILTERS.map((f) => (
        <button
          key={f.value}
          onClick={() => onChange(f.value)}
          className={`rounded-full px-3 py-1 text-sm font-medium transition ${
            value === f.value
              ? 'bg-indigo-600 text-white'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300'
          }`}
        >
          {f.label}
        </button>
      ))}
    </div>
  )
}
