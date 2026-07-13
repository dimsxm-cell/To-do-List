import { strings } from '../copy/strings'
import type { FilterValue } from '../lib/taskUtils'

const MESSAGE: Record<FilterValue, string> = {
  all: strings.tasks.emptyAll,
  active: strings.tasks.emptyActive,
  completed: strings.tasks.emptyCompleted,
}

export function EmptyState({ filter }: { filter: FilterValue }) {
  return <p className="py-12 text-center text-sm text-slate-400">{MESSAGE[filter]}</p>
}
