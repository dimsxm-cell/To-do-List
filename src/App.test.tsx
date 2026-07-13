import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'
import { useAuth } from './hooks/useAuth'
import { useTasks } from './hooks/useTasks'
import { strings } from './copy/strings'

vi.mock('./hooks/useAuth')
vi.mock('./hooks/useTasks')

function baseTasksHook(overrides = {}) {
  return {
    tasks: [],
    loading: false,
    error: null,
    filter: 'all',
    setFilter: vi.fn(),
    addTask: vi.fn(),
    updateTask: vi.fn(),
    deleteTask: vi.fn(),
    toggleComplete: vi.fn(),
    reorderTasks: vi.fn(),
    ...overrides,
  } as any
}

describe('App', () => {
  it('shows the loading state while auth resolves', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null, loading: true, error: null, signIn: vi.fn(), signUp: vi.fn(), signOut: vi.fn(),
    } as any)
    vi.mocked(useTasks).mockReturnValue(baseTasksHook())

    render(<App />)
    expect(screen.getByText(strings.common.loading)).toBeInTheDocument()
  })

  it('shows AuthView when not logged in', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null, loading: false, error: null, signIn: vi.fn(), signUp: vi.fn(), signOut: vi.fn(),
    } as any)
    vi.mocked(useTasks).mockReturnValue(baseTasksHook())

    render(<App />)
    expect(screen.getByPlaceholderText(strings.auth.emailPlaceholder)).toBeInTheDocument()
  })

  it('shows TasksView with the user email as heading when logged in', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 'u1', email: 'dimsxm@gmail.com' }, loading: false, error: null, signIn: vi.fn(), signUp: vi.fn(), signOut: vi.fn(),
    } as any)
    vi.mocked(useTasks).mockReturnValue(baseTasksHook())

    render(<App />)
    expect(screen.getByText('dimsxm@gmail.com')).toBeInTheDocument()
    expect(screen.getByText(strings.tasks.emptyAll)).toBeInTheDocument()
  })
})
