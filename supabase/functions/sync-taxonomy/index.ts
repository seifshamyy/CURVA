Deno.serve(async (_req) => {
  const url = Deno.env.get("AGENT_SERVICE_URL");
  const key = Deno.env.get("AGENT_API_KEY");
  if (!url || !key) {
    return new Response(
      JSON.stringify({ ok: false, error: "missing AGENT_SERVICE_URL or AGENT_API_KEY" }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
  const startedAt = new Date().toISOString();
  const r = await fetch(`${url}/admin/sync-taxonomy`, {
    method: "POST",
    headers: { "X-API-Key": key, "Content-Type": "application/json" },
  });
  const body = await r.text();
  return new Response(
    JSON.stringify({ triggered_at: startedAt, status: r.status, body }),
    { status: r.ok ? 200 : 502, headers: { "Content-Type": "application/json" } },
  );
});