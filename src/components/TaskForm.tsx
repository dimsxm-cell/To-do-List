import { useState, type FormEvent } from 'react'
import { strings } from '../copy/strings'
import type { Priority, TaskInput } from '../types/task'

export function TaskForm({ onAdd }: { onAdd: (input: TaskInput) => void }) {
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [dueDate, setDueDate] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    onAdd({ title: title.trim(), priority, dueDate: dueDate || null })
    setTitle('')
    setPriority('medium')
    setDueDate('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder={strings.tasks.addPlaceholder}
        className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-slate-600 dark:bg-slate-800 dark:text-white"
      />
      <select
        value={priority}
        onChange={(e) => setPriority(e.target.value as Priority)}
        className="rounded-lg border border-slate-200 px-2 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-white"
      >
        <option value="low">{strings.tasks.priorityLow}</option>
        <option value="medium">{strings.tasks.priorityMedium}</option>
        <option value="high">{strings.tasks.priorityHigh}</option>
      </select>
      <input
        type="date"
        value={dueDate}
        onChange={(e) => setDueDate(e.target.value)}
        className="rounded-lg border border-slate-200 px-2 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-white dark:[color-scheme:dark]"
      />
      <button
        type="submit"
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
      >
        {strings.tasks.addButton}
      </button>
    </form>
  )
}
