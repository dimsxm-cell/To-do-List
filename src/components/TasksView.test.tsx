import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TasksView, capitalizeFirst } from './TasksView'
import { ToastProvider } from './Toast'
import { strings } from '../copy/strings'

describe('capitalizeFirst', () => {
  it('uppercases only the first character, leaving the rest untouched', () => {
    expect(capitalizeFirst('dimanche 13 juillet 2026')).toBe('Dimanche 13 juillet 2026')
  })

  it('does not capitalize every word (unlike CSS text-transform: capitalize)', () => {
    expect(capitalizeFirst('dimanche 13 juillet 2026')).not.toBe('Dimanche 13 Juillet 2026')
  })
})

function makeHook(overrides = {}) {
  return {
    tasks: [],
    loading: false,
    error: null,
    filter: 'all',
    setFilter: vi.fn(),
    addTask: vi.fn().mockResolvedValue(true),
    updateTask: vi.fn().mockResolvedValue(true),
    deleteTask: vi.fn().mockResolvedValue(true),
    toggleComplete: vi.fn(),
    reorderTasks: vi.fn(),
    ...overrides,
  } as any
}

function renderView(hook = makeHook(), onSignOut = vi.fn().mockResolvedValue(undefined), userEmail = 'test@example.com') {
  return render(
    <ToastProvider>
      <TasksView tasksHook={hook} onSignOut={onSignOut} userEmail={userEmail} />
    </ToastProvider>
  )
}

describe('TasksView', () => {
  it('shows the empty state when there are no tasks', () => {
    renderView()
    expect(screen.getByText(strings.tasks.emptyAll)).toBeInTheDocument()
  })

  it('shows the signed-in user email as the heading', () => {
    renderView(makeHook(), vi.fn(), 'dimsxm@gmail.com')
    expect(screen.getByText('dimsxm@gmail.com')).toBeInTheDocument()
  })

  it('falls back to the generic heading when there is no user email', () => {
    renderView(makeHook(), vi.fn(), null as any)
    expect(screen.getByText(strings.tasks.heading)).toBeInTheDocument()
  })

  it('calls onSignOut and shows a farewell toast when sign-out clicked', async () => {
    const onSignOut = vi.fn().mockResolvedValue(undefined)
    renderView(makeHook(), onSignOut)
    fireEvent.click(screen.getByText(strings.common.signOut))
    expect(onSignOut).toHaveBeenCalled()
    expect(await screen.findByText(strings.toast.signedOut)).toBeInTheDocument()
  })

  it('shows a warm generic error toast when tasksHook.error is set', async () => {
    const hook = makeHook({ error: 'network down' })
    renderView(hook)
    expect(await screen.findByText(strings.toast.genericError)).toBeInTheDocument()
  })

  it('adds a task through the form and shows a toast', async () => {
    const hook = makeHook()
    renderView(hook)

    fireEvent.change(screen.getByPlaceholderText(strings.tasks.addPlaceholder), { target: { value: 'Buy milk' } })
    fireEvent.click(screen.getByText(strings.tasks.addButton))

    await screen.findByText(strings.toast.taskAdded)
    expect(hook.addTask).toHaveBeenCalledWith({ title: 'Buy milk', priority: 'medium', dueDate: null })
  })

  it('does not show a success toast when addTask fails', async () => {
    const hook = makeHook({ addTask: vi.fn().mockResolvedValue(false) })
    renderView(hook)

    fireEvent.change(screen.getByPlaceholderText(strings.tasks.addPlaceholder), { target: { value: 'Buy milk' } })
    fireEvent.click(screen.getByText(strings.tasks.addButton))

    await Promise.resolve()
    expect(screen.queryByText(strings.toast.taskAdded)).not.toBeInTheDocument()
  })

  it('renders a task item for each task', () => {
    const hook = makeHook({
      tasks: [
        { id: 't1', title: 'Buy milk', completed: false, priority: 'medium', dueDate: null, position: 0, createdAt: '2026-07-12' },
      ],
    })
    renderView(hook)
    expect(screen.getByText('Buy milk')).toBeInTheDocument()
  })

  it('renaming a task calls updateTask with the new title', () => {
    const hook = makeHook({
      tasks: [
        { id: 't1', title: 'Buy milk', completed: false, priority: 'medium', dueDate: null, position: 0, createdAt: '2026-07-12' },
      ],
    })
    renderView(hook)

    fireEvent.click(screen.getByText('Buy milk'))
    const input = screen.getByDisplayValue('Buy milk')
    fireEvent.change(input, { target: { value: 'Buy oat milk' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(hook.updateTask).toHaveBeenCalledWith('t1', { title: 'Buy oat milk' })
  })
})
