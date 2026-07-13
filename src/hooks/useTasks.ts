import { useCallback, useEffect, useState } from 'react'
import type { Task, TaskInput } from '../types/task'
import { filterTasks, sortTasks, type FilterValue } from '../lib/taskUtils'
import * as taskApi from '../lib/taskApi'

interface UseTasksResult {
  tasks: Task[]
  loading: boolean
  error: string | null
  filter: FilterValue
  setFilter: (filter: FilterValue) => void
  addTask: (input: TaskInput) => Promise<boolean>
  updateTask: (id: string, patch: Partial<TaskInput>) => Promise<boolean>
  deleteTask: (id: string) => Promise<boolean>
  toggleComplete: (id: string) => Promise<void>
  reorderTasks: (orderedIds: string[]) => Promise<void>
}

export function useTasks(userId: string | null): UseTasksResult {
  const [allTasks, setAllTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterValue>('all')

  useEffect(() => {
    if (!userId) {
      setAllTasks([])
      setLoading(false)
      return
    }
    setLoading(true)
    taskApi
      .fetchTasks(userId)
      .then((tasks) => setAllTasks(sortTasks(tasks)))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false))
  }, [userId])

  const addTask = useCallback(
    async (input: TaskInput) => {
      if (!userId) return false
      setError(null)
      const position = allTasks.length
      try {
        const created = await taskApi.insertTask(userId, input, position)
        setAllTasks((prev) => sortTasks([...prev, created]))
        return true
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
        return false
      }
    },
    [userId, allTasks.length]
  )

  const updateTask = useCallback(
    async (id: string, patch: Partial<TaskInput>) => {
      setError(null)
      const previous = allTasks
      setAllTasks((prev) =>
        prev.map((t) => (t.id === id ? { ...t, ...patch, dueDate: patch.dueDate !== undefined ? patch.dueDate : t.dueDate } : t))
      )
      try {
        const updated = await taskApi.updateTaskRow(id, patch)
        setAllTasks((prev) => sortTasks(prev.map((t) => (t.id === id ? updated : t))))
        return true
      } catch (err) {
        setAllTasks(previous)
        setError(err instanceof Error ? err.message : String(err))
        return false
      }
    },
    [allTasks]
  )

  const toggleComplete = useCallback(
    async (id: string) => {
      const target = allTasks.find((t) => t.id === id)
      if (!target) return
      setError(null)
      const previous = allTasks
      setAllTasks((prev) => prev.map((t) => (t.id === id ? { ...t, completed: !t.completed } : t)))
      try {
        const updated = await taskApi.updateTaskRow(id, { completed: !target.completed })
        setAllTasks((prev) => sortTasks(prev.map((t) => (t.id === id ? updated : t))))
      } catch (err) {
        setAllTasks(previous)
        setError(err instanceof Error ? err.message : String(err))
      }
    },
    [allTasks]
  )

  const deleteTask = useCallback(
    async (id: string) => {
      setError(null)
      const previous = allTasks
      setAllTasks((prev) => prev.filter((t) => t.id !== id))
      try {
        await taskApi.deleteTaskRow(id)
        return true
      } catch (err) {
        setAllTasks(previous)
        setError(err instanceof Error ? err.message : String(err))
        return false
      }
    },
    [allTasks]
  )

  const reorderTasks = useCallback(
    async (orderedIds: string[]) => {
      setError(null)
      const previous = allTasks
      // orderedIds only covers the currently-visible (filtered) subset. Walk the
      // full list in its current order and substitute the moved subset's new
      // order in place, so tasks hidden by the active filter are never dropped.
      const movedQueue = [...orderedIds]
      const merged = sortTasks(allTasks).map((task) => {
        if (!orderedIds.includes(task.id)) return task
        const nextId = movedQueue.shift()!
        return allTasks.find((t) => t.id === nextId)!
      })
      const reordered = merged.map((task, index) => ({ ...task, position: index }))
      setAllTasks(reordered)
      try {
        await taskApi.reorderTaskRows(reordered.map((t) => ({ id: t.id, position: t.position })))
      } catch (err) {
        setAllTasks(previous)
        setError(err instanceof Error ? err.message : String(err))
      }
    },
    [allTasks]
  )

  return {
    tasks: filterTasks(allTasks, filter),
    loading,
    error,
    filter,
    setFilter,
    addTask,
    updateTask,
    deleteTask,
    toggleComplete,
    reorderTasks,
  }
}
