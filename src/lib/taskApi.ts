import { supabase } from './supabase'
import type { Task, TaskInput } from '../types/task'

interface TaskRow {
  id: string
  title: string
  completed: boolean
  priority: 'low' | 'medium' | 'high'
  due_date: string | null
  position: number
  created_at: string
}

function rowToTask(row: TaskRow): Task {
  return {
    id: row.id,
    title: row.title,
    completed: row.completed,
    priority: row.priority,
    dueDate: row.due_date,
    position: row.position,
    createdAt: row.created_at,
  }
}

export async function fetchTasks(userId: string): Promise<Task[]> {
  const { data, error } = await supabase
    .from('tasks')
    .select('*')
    .eq('user_id', userId)
    .order('position', { ascending: true })

  if (error) throw error
  return (data as TaskRow[]).map(rowToTask)
}

export async function insertTask(userId: string, input: TaskInput, position: number): Promise<Task> {
  const { data, error } = await supabase
    .from('tasks')
    .insert({
      user_id: userId,
      title: input.title,
      priority: input.priority ?? 'medium',
      due_date: input.dueDate ?? null,
      position,
    })
    .select()
    .single()

  if (error) throw error
  return rowToTask(data as TaskRow)
}

export async function updateTaskRow(
  id: string,
  patch: Partial<TaskInput & { completed: boolean }>
): Promise<Task> {
  const dbPatch: Record<string, unknown> = {}
  if (patch.title !== undefined) dbPatch.title = patch.title
  if (patch.priority !== undefined) dbPatch.priority = patch.priority
  if (patch.dueDate !== undefined) dbPatch.due_date = patch.dueDate
  if (patch.completed !== undefined) dbPatch.completed = patch.completed

  const { data, error } = await supabase
    .from('tasks')
    .update(dbPatch)
    .eq('id', id)
    .select()
    .single()

  if (error) throw error
  return rowToTask(data as TaskRow)
}

export async function deleteTaskRow(id: string): Promise<void> {
  const { error } = await supabase.from('tasks').delete().eq('id', id)
  if (error) throw error
}

export async function reorderTaskRows(updates: { id: string; position: number }[]): Promise<void> {
  const results = await Promise.all(
    updates.map(({ id, position }) => supabase.from('tasks').update({ position }).eq('id', id))
  )
  const firstError = results.find((r) => r.error)?.error
  if (firstError) throw firstError
}
