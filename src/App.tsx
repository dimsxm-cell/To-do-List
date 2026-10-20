import { Suspense, lazy } from 'react'
import { useAuth } from './hooks/useAuth'
import { useTasks } from './hooks/useTasks'
import { AuthView } from './components/AuthView'
import { ThemeToggle } from './components/ThemeToggle'
import { ToastProvider } from './components/Toast'
import { strings } from './copy/strings'

// Only signed-in users ever reach the task list, so its drag-and-drop stack
// (@dnd-kit) is fetched on demand instead of shipping with the first paint.
const TasksView = lazy(() =>
  import('./components/TasksView').then((m) => ({ default: m.TasksView }))
)

function LoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">
      {strings.common.loading}
    </div>
  )
}

function AppContent() {
  const auth = useAuth()
  const tasksHook = useTasks(auth.user?.id ?? null)

  if (auth.loading) {
    return <LoadingScreen />
  }

  return (
    <>
      <ThemeToggle />
      {auth.user ? (
        <Suspense fallback={<LoadingScreen />}>
          <TasksView tasksHook={tasksHook} onSignOut={auth.signOut} userEmail={auth.user.email ?? null} />
        </Suspense>
      ) : (
        <AuthView auth={auth} />
      )}
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
