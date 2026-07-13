import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmptyState } from './EmptyState'
import { strings } from '../copy/strings'

describe('EmptyState', () => {
  it('shows the "all" empty message', () => {
    render(<EmptyState filter="all" />)
    expect(screen.getByText(strings.tasks.emptyAll)).toBeInTheDocument()
  })

  it('shows the "active" empty message', () => {
    render(<EmptyState filter="active" />)
    expect(screen.getByText(strings.tasks.emptyActive)).toBeInTheDocument()
  })

  it('shows the "completed" empty message', () => {
    render(<EmptyState filter="completed" />)
    expect(screen.getByText(strings.tasks.emptyCompleted)).toBeInTheDocument()
  })
})
