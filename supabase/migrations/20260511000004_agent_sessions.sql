create table if not exists agent_sessions (
  session_id            text primary key,
  locale                text not null default 'ar',
  customer_name         text,
  focus_product_ids     int[] not null default '{}',
  last_filters          jsonb,
  conversation_summary  text default '',
  turn_count            int not null default 0,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  last_active_at        timestamptz not null default now()
);

create index if not exists agent_sessions_last_active_at_idx
  on agent_sessions(last_active_at);

-- Daily cleanup of inactive sessions (>30d). Uses pg_cron.
create extension if not exists pg_cron;
do $$
begin
  perform cron.schedule(
    'agent-sessions-gc-daily',
    '15 2 * * *',
    $cron$
    delete from agent_sessions
    where last_active_at < now() - interval '30 days';
    $cron$
  );
exception when others then
  raise notice 'cron.schedule skipped: %', sqlerrm;
end$$;