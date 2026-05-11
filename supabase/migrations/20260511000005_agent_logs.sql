create table if not exists agent_logs (
  id                bigserial primary key,
  session_id        text not null,
  user_message      text not null,
  reply_text        text,
  intent            text,
  tool_calls        jsonb,
  product_ids       int[],
  model             text,
  prompt_tokens     int,
  completion_tokens int,
  cached_tokens     int,
  latency_ms        int,
  ok                boolean not null,
  error             text,
  created_at        timestamptz not null default now()
);

create index if not exists agent_logs_session_created_idx
  on agent_logs(session_id, created_at desc);
create index if not exists agent_logs_created_idx
  on agent_logs(created_at desc);
create index if not exists agent_logs_failures_idx
  on agent_logs(created_at desc) where ok = false;