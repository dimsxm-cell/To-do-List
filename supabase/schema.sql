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
