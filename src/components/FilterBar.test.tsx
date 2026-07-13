import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FilterBar } from './FilterBar'
import { strings } from '../copy/strings'

describe('FilterBar', () => {
  it('renders all three filter buttons', () => {
    render(<FilterBar value="all" onChange={vi.fn()} />)
    expect(screen.getByText(strings.tasks.filterAll)).toBeInTheDocument()
    expect(screen.getByText(strings.tasks.filterActive)).toBeInTheDocument()
    expect(screen.getByText(strings.tasks.filterCompleted)).toBeInTheDocument()
  })

  it('calls onChange with the clicked filter value', () => {
    const onChange = vi.fn()
    render(<FilterBar value="all" onChange={onChange} />)
    fireEvent.click(screen.getByText(strings.tasks.filterActive))
    expect(onChange).toHaveBeenCalledWith('active')
  })

  it('highlights the active filter', () => {
    render(<FilterBar value="completed" onChange={vi.fn()} />)
    expect(screen.getByText(strings.tasks.filterCompleted).className).toMatch(/bg-indigo-600/)
  })
})
