export type Priority = 'low' | 'medium' | 'high'

export interface Task {
  id: string
  title: string
  completed: boolean
  priority: Priority
  dueDate: string | null
  position: number
  createdAt: string
}

export interface TaskInput {
  title: string
  priority?: Priority
  dueDate?: string | null
}
