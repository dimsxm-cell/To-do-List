import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useTasks } from './useTasks'
import * as taskApi from '../lib/taskApi'

vi.mock('../lib/taskApi')

const TASK_A = { id: 'a', title: 'A', completed: false, priority: 'medium' as const, dueDate: null, position: 0, createdAt: '2026-01-01' }
const TASK_B = { id: 'b', title: 'B', completed: false, priority: 'medium' as const, dueDate: null, position: 1, createdAt: '2026-01-02' }

describe('useTasks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(taskApi.fetchTasks).mockResolvedValue([TASK_A, TASK_B])
    vi.mocked(taskApi.updateTaskRow).mockImplementation(async (id, patch) => ({
      ...(id === 'a' ? TASK_A : TASK_B),
      ...patch,
    }) as any)
  })

  it('loads tasks for the given user', async () => {
    const { result } = renderHook(() => useTasks('user-1'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.tasks).toEqual([TASK_A, TASK_B])
  })

  it('does not fetch when userId is null', async () => {
    const { result } = renderHook(() => useTasks(null))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(taskApi.fetchTasks).not.toHaveBeenCalled()
    expect(result.current.tasks).toEqual([])
  })

  it('toggleComplete optimistically flips completed, then persists', async () => {
    const { result } = renderHook(() => useTasks('user-1'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.toggleComplete('a')
    })

    expect(taskApi.updateTaskRow).toHaveBeenCalledWith('a', { completed: true })
    expect(result.current.tasks.find((t) => t.id === 'a')?.completed).toBe(true)
  })

  it('toggleComplete rolls back on error', async () => {
    vi.mocked(taskApi.updateTaskRow).mockRejectedValueOnce(new Error('network down'))
    const { result } = renderHook(() => useTasks('user-1'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.toggleComplete('a')
    })

    expect(result.current.tasks.find((t) => t.id === 'a')?.completed).toBe(false)
    expect(result.current.error).toBe('network down')
  })

  it('setFilter narrows the returned tasks', async () => {
    const { result } = renderHook(() => useTasks('user-1'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.toggleComplete('a')
    })
    act(() => {
      result.current.setFilter('completed')
    })

    expect(result.current.tasks.map((t) => t.id)).toEqual(['a'])
  })

  it('updateTask with explicit null dueDate clears the due date', async () => {
    const taskWithDueDate = { ...TASK_A, dueDate: '2026-12-25' }
    vi.mocked(taskApi.fetchTasks).mockResolvedValueOnce([taskWithDueDate, TASK_B])
    vi.mocked(taskApi.updateTaskRow).mockResolvedValueOnce({ ...taskWithDueDate, dueDate: null })

    const { result } = renderHook(() => useTasks('user-1'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.tasks.find((t) => t.id === 'a')?.dueDate).toBe('2026-12-25')

    await act(async () => {
      await result.current.updateTask('a', { dueDate: null })
    })

    expect(result.current.tasks.find((t) => t.id === 'a')?.dueDate).toBe(null)
  })

  it('updateTask uses server response to resync state', async () => {
    const serverResponse = { ...TASK_A, title: 'Updated Title', priority: 'high' as const }
    vi.mocked(taskApi.updateTaskRow).mockResolvedValueOnce(serverResponse)

    const { result } = renderHook(() => useTasks('user-1'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.updateTask('a', { title: 'New Title' })
    })

    const updatedTask = result.current.tasks.find((t) => t.id === 'a')
    expect(updatedTask?.title).toBe('Updated Title')
    expect(updatedTask?.priority).toBe('high')
  })

  it('toggleComplete uses server response to resync state', async () => {
    const serverResponse = { ...TASK_A, completed: true, position: 5 }
    vi.mocked(taskApi.updateTaskRow).mockResolvedValueOnce(serverResponse)

    const { result } = renderHook(() => useTasks('user-1'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.toggleComplete('a')
    })

    const updatedTask = result.current.tasks.find((t) => t.id === 'a')
    expect(updatedTask?.completed).toBe(true)
    expect(updatedTask?.position).toBe(5)
  })
})
