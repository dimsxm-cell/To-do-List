# To-Do App

Single-page to-do app: React + TypeScript + Tailwind CSS + Supabase (auth + database). No routing.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Create a Supabase project at https://supabase.com, then run `supabase/schema.sql`
   in the Supabase SQL editor to create the `tasks` table and its RLS policy.

3. Copy `.env.example` to `.env` and fill in your project's URL and anon key
   (Project Settings → API in the Supabase dashboard):
   ```bash
   cp .env.example .env
   ```

4. Start the dev server:
   ```bash
   npm run dev
   ```

## Scripts

- `npm run dev` — start the Vite dev server
- `npm run build` — typecheck and build for production
- `npm test` — run the test suite once
- `npm run test:watch` — run tests in watch mode
- `npm run typecheck` — run `tsc --noEmit` only

## Project structure

- `src/hooks/` — `useAuth`, `useTasks`: all business logic and Supabase access
- `src/lib/` — Supabase client, task data-access layer, pure filter/sort utils
- `src/copy/strings.ts` — every piece of user-facing text
- `src/components/` — presentational components consuming the hooks and copy
- `supabase/schema.sql` — database schema and row-level security policy
