import type { Task } from '../types/task'

export type FilterValue = 'all' | 'active' | 'completed'

export function filterTasks(tasks: Task[], filter: FilterValue): Task[] {
  if (filter === 'active') return tasks.filter((t) => !t.completed)
  if (filter === 'completed') return tasks.filter((t) => t.completed)
  return tasks
}

export function sortTasks(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    if (a.position !== b.position) return a.position - b.position
    if (a.dueDate && b.dueDate) return a.dueDate.localeCompare(b.dueDate)
    if (a.dueDate) return -1
    if (b.dueDate) return 1
    return 0
  })
}
