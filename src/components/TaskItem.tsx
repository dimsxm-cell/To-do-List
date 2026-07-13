import { useState, type KeyboardEvent } from 'react'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { motion } from 'framer-motion'
import { strings } from '../copy/strings'
import type { Task } from '../types/task'

const PRIORITY_LABEL: Record<Task['priority'], string> = {
  low: strings.tasks.priorityLow,
  medium: strings.tasks.priorityMedium,
  high: strings.tasks.priorityHigh,
}

const PRIORITY_COLOR: Record<Task['priority'], string> = {
  low: 'bg-slate-200 text-slate-700 dark:bg-slate-600 dark:text-slate-200',
  medium: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-200',
  high: 'bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-200',
}

interface TaskItemProps {
  task: Task
  onToggle: (id: string) => void
  onDelete: (id: string) => void
  onRename: (id: string, title: string) => void
}

export function TaskItem({ task, onToggle, onDelete, onRename }: TaskItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: task.id })
  const [editing, setEditing] = useState(false)
  const [draftTitle, setDraftTitle] = useState(task.title)

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  function commitEdit() {
    setEditing(false)
    const trimmed = draftTitle.trim()
    if (trimmed && trimmed !== task.title) onRename(task.id, trimmed)
    else setDraftTitle(task.title)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') commitEdit()
    if (e.key === 'Escape') {
      setDraftTitle(task.title)
      setEditing(false)
    }
  }

  return (
    <motion.li
      ref={setNodeRef}
      style={style}
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -8 }}
      className="flex items-center gap-3 rounded-xl bg-white p-3 shadow-sm dark:bg-slate-800"
    >
      <button
        {...attributes}
        {...listeners}
        aria-label={strings.tasks.reorderLabel}
        className="cursor-grab text-slate-300 hover:text-slate-500 dark:text-slate-500"
      >
        ⠿
      </button>
      <input
        type="checkbox"
        checked={task.completed}
        onChange={() => onToggle(task.id)}
        className="h-4 w-4 rounded accent-indigo-600"
      />
      <div className="flex-1">
        {editing ? (
          <input
            autoFocus
            value={draftTitle}
            onChange={(e) => setDraftTitle(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={handleKeyDown}
            className="w-full rounded border border-indigo-300 bg-transparent px-1 text-sm text-slate-800 outline-none dark:text-white"
          />
        ) : (
          <p
            onClick={() => setEditing(true)}
            className={`cursor-text text-sm ${task.completed ? 'text-slate-400 line-through' : 'text-slate-800 dark:text-white'}`}
          >
            {task.title}
          </p>
        )}
        {task.dueDate && (
          <p className="text-xs text-slate-400">
            {strings.tasks.dueDateLabel}: {task.dueDate}
          </p>
        )}
      </div>
      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${PRIORITY_COLOR[task.priority]}`}>
        {PRIORITY_LABEL[task.priority]}
      </span>
      <button
        onClick={() => onDelete(task.id)}
        aria-label={strings.tasks.deleteConfirm}
        className="text-slate-300 hover:text-rose-500 dark:text-slate-500"
      >
        ✕
      </button>
    </motion.li>
  )
}
