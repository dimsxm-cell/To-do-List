import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchTasks, insertTask, updateTaskRow, deleteTaskRow, reorderTaskRows } from './taskApi'
import { supabase } from './supabase'

vi.mock('./supabase', () => ({
  supabase: { from: vi.fn() },
}))

function createMockQuery(result: { data: unknown; error: unknown }) {
  const query: any = {
    select: vi.fn(() => query),
    insert: vi.fn(() => query),
    update: vi.fn(() => query),
    delete: vi.fn(() => query),
    eq: vi.fn(() => query),
    order: vi.fn(() => query),
    single: vi.fn(() => query),
    then: (resolve: (value: typeof result) => void) => resolve(result),
  }
  return query
}

const ROW = {
  id: 't1',
  title: 'Buy milk',
  completed: false,
  priority: 'medium' as const,
  due_date: null,
  position: 0,
  created_at: '2026-07-12T00:00:00.000Z',
}

describe('taskApi', () => {
  beforeEach(() => {
    vi.mocked(supabase.from).mockReset()
  })

  it('fetchTasks maps rows to Task objects', async () => {
    vi.mocked(supabase.from).mockReturnValue(createMockQuery({ data: [ROW], error: null }))

    const tasks = await fetchTasks('user-1')

    expect(supabase.from).toHaveBeenCalledWith('tasks')
    expect(tasks).toEqual([
      { id: 't1', title: 'Buy milk', completed: false, priority: 'medium', dueDate: null, position: 0, createdAt: '2026-07-12T00:00:00.000Z' },
    ])
  })

  it('fetchTasks throws on error', async () => {
    vi.mocked(supabase.from).mockReturnValue(createMockQuery({ data: null, error: new Error('boom') }))

    await expect(fetchTasks('user-1')).rejects.toThrow('boom')
  })

  it('insertTask sends defaults for optional fields', async () => {
    vi.mocked(supabase.from).mockReturnValue(createMockQuery({ data: ROW, error: null }))

    const task = await insertTask('user-1', { title: 'Buy milk' }, 0)

    expect(task.title).toBe('Buy milk')
    expect(task.priority).toBe('medium')
  })

  it('updateTaskRow maps a completed patch to the db column', async () => {
    const query = createMockQuery({ data: { ...ROW, completed: true }, error: null })
    vi.mocked(supabase.from).mockReturnValue(query)

    const task = await updateTaskRow('t1', { completed: true })

    expect(query.update).toHaveBeenCalledWith({ completed: true })
    expect(task.completed).toBe(true)
  })

  it('deleteTaskRow calls delete + eq with id', async () => {
    const query = createMockQuery({ data: null, error: null })
    vi.mocked(supabase.from).mockReturnValue(query)

    await deleteTaskRow('t1')

    expect(query.delete).toHaveBeenCalled()
    expect(query.eq).toHaveBeenCalledWith('id', 't1')
  })

  it('reorderTaskRows updates each task position', async () => {
    const query = createMockQuery({ data: null, error: null })
    vi.mocked(supabase.from).mockReturnValue(query)

    await reorderTaskRows([{ id: 't1', position: 1 }, { id: 't2', position: 0 }])

    expect(query.update).toHaveBeenCalledWith({ position: 1 })
    expect(query.update).toHaveBeenCalledWith({ position: 0 })
  })
})
