# To-Do App — Design

**Date:** 2026-07-12
**Statut:** Approuvé

## Contexte

Application de to-do en une seule page, sans routing, avec authentification et
persistance via Supabase. Le travail de conception se répartit selon 3 rôles
(Copy, Design & UI, Features), même si l'implémentation est faite en une seule
passe cohérente plutôt que par 3 agents séparés.

## Stack

- **Build** : Vite + React + TypeScript
- **Style** : Tailwind CSS
- **Backend** : Supabase (Auth email/mot de passe + Postgres + RLS)
- **State/data** : hooks custom (`useAuth`, `useTasks`) appelant directement le
  client Supabase, avec updates optimistes. TanStack Query écarté — inutile
  pour une seule page mono-utilisateur sans besoin de cache multi-vues.
- **Drag-and-drop** : `@dnd-kit` — léger, accessible. Le drag HTML5 natif a
  été écarté pour son manque de fluidité et de support tactile.
- **Animations** : `framer-motion` pour les micro-interactions (apparition/
  suppression de tâche, transitions de vue). CSS pur écarté car plus dur à
  maintenir pour des transitions de liste réordonnable.
- **Notifications** : système de toast maison (contrôle total sur le ton).

## Architecture & flux

Une seule page (`App.tsx`). `useAuth()` détermine l'état :
chargement / non connecté / connecté. Rendu conditionnel, pas de router :

- **Non connecté** → `AuthView` (formulaire connexion/inscription, bascule
  entre les deux modes sur le même écran)
- **Connecté** → `TasksView` (liste des tâches + formulaire d'ajout + filtres)

Supabase persiste la session (refresh token en localStorage) : un refresh de
page garde l'utilisateur connecté.

## Structure de fichiers

```
src/
  lib/
    supabase.ts          # client Supabase
  types/
    task.ts              # Task, Priority, TaskInput (types partagés)
  hooks/                  # ── Features ──
    useAuth.ts
    useTasks.ts
  copy/                   # ── Copy ──
    strings.ts            # tous les textes de l'app, par clé
  components/             # ── Design (consomme hooks + copy) ──
    AuthView.tsx
    TasksView.tsx
    TaskItem.tsx
    TaskForm.tsx
    FilterBar.tsx
    EmptyState.tsx
    Toast.tsx
  App.tsx
  main.tsx
supabase/
  schema.sql              # table tasks + RLS policies
.env.example
```

`copy/strings.ts` centralise tout le texte : aucune chaîne de caractères en
dur dans les composants de `components/`.

## Modèle de données (Supabase)

```sql
create table tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users not null,
  title text not null,
  completed boolean not null default false,
  priority text not null check (priority in ('low','medium','high')) default 'medium',
  due_date date,
  position int not null,
  created_at timestamptz not null default now()
);

alter table tasks enable row level security;

create policy "Users manage their own tasks"
  on tasks for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
```

`position` sert à l'ordre de réorganisation par drag-and-drop.

## Types partagés (`types/task.ts`)

```ts
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
```

## Hooks exposés (Features)

- `useAuth()` → `{ user, loading, signIn, signUp, signOut, error }`
- `useTasks()` → `{ tasks, loading, error, addTask, updateTask, deleteTask,
  toggleComplete, reorderTasks, filter, setFilter }`
  - `filter`: `'all' | 'active' | 'completed'`
  - Tri : `position` puis `dueDate`

Les composants de `components/` consomment ces hooks et n'implémentent
aucune logique métier ni appel Supabase direct.

## Fonctionnalités (v1)

- CRUD complet des tâches + marquer comme terminé
- Priorité (basse/moyenne/haute) et date d'échéance optionnelle
- Filtres : toutes / actives / terminées
- Réorganisation manuelle par drag-and-drop (persistée via `position`)

## États nécessitant du Copy

Chargement initial, liste vide (aucune tâche), liste vide après filtre,
erreur réseau/auth, succès connexion/inscription, tâche ajoutée/supprimée,
placeholder du champ titre, placeholders email/mot de passe.

## Design visuel

- Palette sombre premium par défaut, bascule clair/sombre
- Une seule couleur d'accent, typographie soignée (Inter ou police système)
- Carte de tâche avec ombre douce, drag handle visible au survol
- Animations d'apparition/suppression de tâche
- Responsive mobile-first (formulaire empilé sur mobile)

## Hors scope (v1)

- Partage de tâches entre utilisateurs
- Sous-tâches / catégories / tags
- Notifications push pour les échéances
- Recherche texte libre
