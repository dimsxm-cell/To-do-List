import { useEffect } from 'react'
import { DndContext, closestCenter, type DragEndEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { AnimatePresence } from 'framer-motion'
import { strings } from '../copy/strings'
import { useToast } from './Toast'
import type { useTasks } from '../hooks/useTasks'
import { TaskForm } from './TaskForm'
import { TaskItem } from './TaskItem'
import { FilterBar } from './FilterBar'
import { EmptyState } from './EmptyState'

type TasksHook = ReturnType<typeof useTasks>

export function TasksView({ tasksHook, onSignOut }: { tasksHook: TasksHook; onSignOut: () => Promise<void> }) {
  const { showToast } = useToast()
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  useEffect(() => {
    if (tasksHook.error) showToast(strings.toast.genericError, 'error')
  }, [tasksHook.error, showToast])

  async function handleAdd(input: Parameters<TasksHook['addTask']>[0]) {
    const success = await tasksHook.addTask(input)
    if (success) showToast(strings.toast.taskAdded)
  }

  async function handleDelete(id: string) {
    const success = await tasksHook.deleteTask(id)
    if (success) showToast(strings.toast.taskDeleted)
  }

  async function handleRename(id: string, title: string) {
    const success = await tasksHook.updateTask(id, { title })
    if (success) showToast(strings.toast.taskUpdated)
  }

  async function handleSignOut() {
    await onSignOut()
    showToast(strings.toast.signedOut)
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const ids = tasksHook.tasks.map((t) => t.id)
    const oldIndex = ids.indexOf(String(active.id))
    const newIndex = ids.indexOf(String(over.id))
    const reordered = [...ids]
    reordered.splice(oldIndex, 1)
    reordered.splice(newIndex, 0, String(active.id))
    tasksHook.reorderTasks(reordered)
  }

  return (
    <div className="mx-auto max-w-xl px-4 py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">{strings.tasks.heading}</h1>
        <button onClick={handleSignOut} className="text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
          {strings.common.signOut}
        </button>
      </div>

      <TaskForm onAdd={handleAdd} />

      <div className="mb-4 mt-6">
        <FilterBar value={tasksHook.filter} onChange={tasksHook.setFilter} />
      </div>

      {tasksHook.tasks.length === 0 ? (
        <EmptyState filter={tasksHook.filter} />
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={tasksHook.tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
            <ul className="flex flex-col gap-2">
              <AnimatePresence>
                {tasksHook.tasks.map((task) => (
                  <TaskItem
                    key={task.id}
                    task={task}
                    onToggle={tasksHook.toggleComplete}
                    onDelete={handleDelete}
                    onRename={handleRename}
                  />
                ))}
              </AnimatePresence>
            </ul>
          </SortableContext>
        </DndContext>
      )}
    </div>
  )
}
