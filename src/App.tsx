import { useAuth } from './hooks/useAuth'
import { useTasks } from './hooks/useTasks'
import { AuthView } from './components/AuthView'
import { TasksView } from './components/TasksView'
import { ThemeToggle } from './components/ThemeToggle'
import { ToastProvider } from './components/Toast'
import { strings } from './copy/strings'

function AppContent() {
  const auth = useAuth()
  const tasksHook = useTasks(auth.user?.id ?? null)

  if (auth.loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">
        {strings.common.loading}
      </div>
    )
  }

  return (
    <>
      <ThemeToggle />
      {auth.user ? <TasksView tasksHook={tasksHook} onSignOut={auth.signOut} /> : <AuthView auth={auth} />}
    </>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <AppContent />
    </ToastProvider>
  )
}
