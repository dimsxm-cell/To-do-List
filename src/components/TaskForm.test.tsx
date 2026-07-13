import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TaskForm } from './TaskForm'
import { strings } from '../copy/strings'

describe('TaskForm', () => {
  it('calls onAdd with trimmed title and defaults', () => {
    const onAdd = vi.fn()
    render(<TaskForm onAdd={onAdd} />)

    fireEvent.change(screen.getByPlaceholderText(strings.tasks.addPlaceholder), { target: { value: '  Buy milk  ' } })
    fireEvent.click(screen.getByText(strings.tasks.addButton))

    expect(onAdd).toHaveBeenCalledWith({ title: 'Buy milk', priority: 'medium', dueDate: null })
  })

  it('does not call onAdd when title is empty', () => {
    const onAdd = vi.fn()
    render(<TaskForm onAdd={onAdd} />)

    fireEvent.click(screen.getByText(strings.tasks.addButton))

    expect(onAdd).not.toHaveBeenCalled()
  })

  it('clears the title field after submit', () => {
    const onAdd = vi.fn()
    render(<TaskForm onAdd={onAdd} />)
    const input = screen.getByPlaceholderText(strings.tasks.addPlaceholder) as HTMLInputElement

    fireEvent.change(input, { target: { value: 'Buy milk' } })
    fireEvent.click(screen.getByText(strings.tasks.addButton))

    expect(input.value).toBe('')
  })
})
