import { describe, it, expect } from 'vitest'
import { filterTasks, sortTasks } from './taskUtils'
import type { Task } from '../types/task'

function makeTask(overrides: Partial<Task>): Task {
  return {
    id: 'id',
    title: 'title',
    completed: false,
    priority: 'medium',
    dueDate: null,
    position: 0,
    createdAt: '2026-01-01T00:00:00.000Z',
    ...overrides,
  }
}

describe('filterTasks', () => {
  const tasks = [
    makeTask({ id: 'a', completed: false }),
    makeTask({ id: 'b', completed: true }),
  ]

  it('returns all tasks for "all"', () => {
    expect(filterTasks(tasks, 'all')).toEqual(tasks)
  })

  it('returns only incomplete tasks for "active"', () => {
    expect(filterTasks(tasks, 'active').map((t) => t.id)).toEqual(['a'])
  })

  it('returns only completed tasks for "completed"', () => {
    expect(filterTasks(tasks, 'completed').map((t) => t.id)).toEqual(['b'])
  })
})

describe('sortTasks', () => {
  it('sorts by position ascending', () => {
    const tasks = [makeTask({ id: 'a', position: 2 }), makeTask({ id: 'b', position: 0 })]
    expect(sortTasks(tasks).map((t) => t.id)).toEqual(['b', 'a'])
  })

  it('breaks position ties by earliest due date first', () => {
    const tasks = [
      makeTask({ id: 'a', position: 0, dueDate: '2026-08-01' }),
      makeTask({ id: 'b', position: 0, dueDate: '2026-07-01' }),
    ]
    expect(sortTasks(tasks).map((t) => t.id)).toEqual(['b', 'a'])
  })

  it('places tasks with a due date before tasks without one, same position', () => {
    const tasks = [
      makeTask({ id: 'a', position: 0, dueDate: null }),
      makeTask({ id: 'b', position: 0, dueDate: '2026-07-01' }),
    ]
    expect(sortTasks(tasks).map((t) => t.id)).toEqual(['b', 'a'])
  })
})
