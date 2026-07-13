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
  addTask: (input: TaskInput) => Promise<void>
  updateTask: (id: string, patch: Partial<TaskInput>) => Promise<void>
  deleteTask: (id: string) => Promise<void>
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
      if (!userId) return
      setError(null)
      const position = allTasks.length
      try {
        const created = await taskApi.insertTask(userId, input, position)
        setAllTasks((prev) => sortTasks([...prev, created]))
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
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
      } catch (err) {
        setAllTasks(previous)
        setError(err instanceof Error ? err.message : String(err))
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
      } catch (err) {
        setAllTasks(previous)
        setError(err instanceof Error ? err.message : String(err))
      }
    },
    [allTasks]
  )

  const reorderTasks = useCallback(
    async (orderedIds: string[]) => {
      setError(null)
      const previous = allTasks
      const reordered = orderedIds
        .map((id, index) => {
          const task = allTasks.find((t) => t.id === id)
          return task ? { ...task, position: index } : null
        })
        .filter((t): t is Task => t !== null)
      setAllTasks(sortTasks(reordered))
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
