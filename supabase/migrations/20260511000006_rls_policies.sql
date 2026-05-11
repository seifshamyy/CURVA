-- Lock down all tables to service role only. The agent service uses the
-- service role key; nothing else should read or write.

alter table agent_sessions enable row level security;
alter table agent_logs enable row level security;
alter table taxonomy_sync_runs enable row level security;
alter table categories enable row level security;
alter table subcategories enable row level security;
alter table clubs enable row level security;
alter table brands enable row level security;
alter table seasons enable row level security;
alter table branches enable row level security;

-- Service-role-only policies (deny by default; service role bypasses RLS,
-- but we explicitly add the policy for clarity and forward-compat).
do $$ declare t text;
begin
  for t in select unnest(array[
    'agent_sessions','agent_logs','taxonomy_sync_runs',
    'categories','subcategories','clubs','brands','seasons','branches'
  ]) loop
    execute format(
      'create policy %I on %I for all using (auth.role() = ''service_role'') with check (auth.role() = ''service_role'')',
      t || '_service_role_only', t
    );
  end loop;
end$$;