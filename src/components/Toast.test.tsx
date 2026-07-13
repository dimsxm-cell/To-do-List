import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, initial, animate, exit, layout, transition, ...rest }: any) => (
      <div {...rest}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

import { ToastProvider, useToast } from './Toast'

function TestConsumer() {
  const { showToast } = useToast()
  return <button onClick={() => showToast('Tâche ajoutée !')}>fire</button>
}

describe('Toast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows a toast then removes it after 3s', () => {
    render(
      <ToastProvider>
        <TestConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('fire'))
    expect(screen.getByText('Tâche ajoutée !')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    expect(screen.queryByText('Tâche ajoutée !')).not.toBeInTheDocument()
  })

  it('throws when useToast is used outside a provider', () => {
    function Bare() {
      useToast()
      return null
    }
    expect(() => render(<Bare />)).toThrow('useToast must be used within ToastProvider')
  })
})
