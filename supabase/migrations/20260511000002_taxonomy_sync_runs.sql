create table if not exists taxonomy_sync_runs (
  id             bigserial primary key,
  started_at     timestamptz not null,
  finished_at    timestamptz,
  ok             boolean,
  delta_summary  jsonb,
  error          text
);
create index if not exists taxonomy_sync_runs_started_at_idx
  on taxonomy_sync_runs(started_at desc);