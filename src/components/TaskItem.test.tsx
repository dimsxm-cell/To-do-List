import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DndContext } from '@dnd-kit/core'
import { SortableContext } from '@dnd-kit/sortable'
import { TaskItem } from './TaskItem'
import { strings } from '../copy/strings'
import type { Task } from '../types/task'

const TASK: Task = {
  id: 't1',
  title: 'Buy milk',
  completed: false,
  priority: 'high',
  dueDate: '2026-07-15',
  position: 0,
  createdAt: '2026-07-12T00:00:00.000Z',
}

function renderItem(task = TASK, onToggle = vi.fn(), onDelete = vi.fn(), onRename = vi.fn()) {
  return render(
    <DndContext>
      <SortableContext items={[task.id]}>
        <ul>
          <TaskItem task={task} onToggle={onToggle} onDelete={onDelete} onRename={onRename} />
        </ul>
      </SortableContext>
    </DndContext>
  )
}

describe('TaskItem', () => {
  it('renders title, priority and due date', () => {
    renderItem()
    expect(screen.getByText('Buy milk')).toBeInTheDocument()
    expect(screen.getByText(strings.tasks.priorityHigh)).toBeInTheDocument()
    expect(screen.getByText(/2026-07-15/)).toBeInTheDocument()
  })

  it('calls onToggle when checkbox clicked', () => {
    const onToggle = vi.fn()
    renderItem(TASK, onToggle)
    fireEvent.click(screen.getByRole('checkbox'))
    expect(onToggle).toHaveBeenCalledWith('t1')
  })

  it('calls onDelete when delete button clicked', () => {
    const onDelete = vi.fn()
    renderItem(TASK, vi.fn(), onDelete)
    fireEvent.click(screen.getByLabelText(strings.tasks.deleteConfirm))
    expect(onDelete).toHaveBeenCalledWith('t1')
  })

  it('applies line-through style when completed', () => {
    renderItem({ ...TASK, completed: true })
    expect(screen.getByText('Buy milk').className).toMatch(/line-through/)
  })

  it('clicking the title switches to an editable input pre-filled with the title', () => {
    renderItem()
    fireEvent.click(screen.getByText('Buy milk'))
    expect(screen.getByDisplayValue('Buy milk')).toBeInTheDocument()
  })

  it('calls onRename and exits edit mode when Enter is pressed', () => {
    const onRename = vi.fn()
    renderItem(TASK, vi.fn(), vi.fn(), onRename)
    fireEvent.click(screen.getByText('Buy milk'))
    const input = screen.getByDisplayValue('Buy milk')
    fireEvent.change(input, { target: { value: 'Buy oat milk' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onRename).toHaveBeenCalledWith('t1', 'Buy oat milk')
    expect(screen.queryByDisplayValue('Buy oat milk')).not.toBeInTheDocument()
  })

  it('discards the edit and calls no callback when Escape is pressed', () => {
    const onRename = vi.fn()
    renderItem(TASK, vi.fn(), vi.fn(), onRename)
    fireEvent.click(screen.getByText('Buy milk'))
    const input = screen.getByDisplayValue('Buy milk')
    fireEvent.change(input, { target: { value: 'Something else' } })
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(onRename).not.toHaveBeenCalled()
    expect(screen.getByText('Buy milk')).toBeInTheDocument()
  })
})
