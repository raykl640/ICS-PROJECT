// fetch stub: route "METHOD /path" to a JSON body and status; unknown routes are 404.
type Route = { status?: number; body: unknown } | (() => { status?: number; body: unknown });

export function stubFetch(routes: Record<string, Route>) {
  const calls: { method: string; url: string; body: unknown }[] = [];
  const fetchStub = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const path = url.split("?")[0];
    const route = routes[`${method} ${path}`];
    const { status = 200, body } = typeof route === "function" ? route() : (route ?? { status: 404, body: {} });
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchStub);
  return calls;
}
