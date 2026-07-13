import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AuthView } from './AuthView'
import { ToastProvider } from './Toast'
import { strings } from '../copy/strings'

function makeAuth(overrides = {}) {
  return {
    user: null,
    loading: false,
    error: null,
    signIn: vi.fn().mockResolvedValue(true),
    signUp: vi.fn().mockResolvedValue(true),
    signOut: vi.fn(),
    ...overrides,
  } as any
}

function renderAuthView(auth = makeAuth()) {
  return render(
    <ToastProvider>
      <AuthView auth={auth} />
    </ToastProvider>
  )
}

describe('AuthView', () => {
  it('submits sign-in credentials', () => {
    const auth = makeAuth()
    renderAuthView(auth)

    fireEvent.change(screen.getByPlaceholderText(strings.auth.emailPlaceholder), { target: { value: 'a@b.com' } })
    fireEvent.change(screen.getByPlaceholderText(strings.auth.passwordPlaceholder), { target: { value: 'secret1' } })
    fireEvent.click(screen.getByText(strings.auth.submitSignIn))

    expect(auth.signIn).toHaveBeenCalledWith('a@b.com', 'secret1')
  })

  it('switches to sign-up mode', () => {
    renderAuthView()

    fireEvent.click(screen.getByText(strings.auth.switchToSignUp))

    expect(screen.getByText(strings.auth.titleSignUp)).toBeInTheDocument()
  })

  it('shows the auth error message', () => {
    const auth = makeAuth({ error: 'Invalid credentials' })
    renderAuthView(auth)

    expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials')
  })

  it('shows a success toast after a successful sign-in', async () => {
    const auth = makeAuth({ signIn: vi.fn().mockResolvedValue(true) })
    renderAuthView(auth)

    fireEvent.change(screen.getByPlaceholderText(strings.auth.emailPlaceholder), { target: { value: 'a@b.com' } })
    fireEvent.change(screen.getByPlaceholderText(strings.auth.passwordPlaceholder), { target: { value: 'secret1' } })
    fireEvent.click(screen.getByText(strings.auth.submitSignIn))

    expect(await screen.findByText(strings.toast.signedIn)).toBeInTheDocument()
  })

  it('does not show a success toast after a failed sign-in', async () => {
    const auth = makeAuth({ signIn: vi.fn().mockResolvedValue(false) })
    renderAuthView(auth)

    fireEvent.change(screen.getByPlaceholderText(strings.auth.emailPlaceholder), { target: { value: 'a@b.com' } })
    fireEvent.change(screen.getByPlaceholderText(strings.auth.passwordPlaceholder), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByText(strings.auth.submitSignIn))

    await Promise.resolve()
    expect(screen.queryByText(strings.toast.signedIn)).not.toBeInTheDocument()
  })
})
