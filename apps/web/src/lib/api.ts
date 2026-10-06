/** Thin fetch wrapper for the QA Forge API. Errors are RFC 7807 problem+json. */

export const API_PREFIX = "/api/v1";

export interface Problem {
  type?: string;
  title: string;
  status: number;
  detail?: string;
  request_id?: string;
  errors?: { loc: (string | number)[]; msg: string; type: string }[];
}

export class ApiError extends Error {
  constructor(public readonly problem: Problem) {
    super(problem.detail ?? problem.title);
    this.name = "ApiError";
  }

  get status() {
    return this.problem.status;
  }
}

async function toProblem(res: Response): Promise<Problem> {
  const fallback: Problem = { title: res.statusText || "Request failed", status: res.status };
  const type = res.headers.get("content-type") ?? "";
  if (!type.includes("json")) return fallback;
  try {
    const body = (await res.json()) as Partial<Problem>;
    return { ...fallback, ...body, status: body.status ?? res.status };
  } catch {
    return fallback;
  }
}

let refreshInFlight: Promise<boolean> | null = null;

// One refresh at a time: a page that fires several requests after the access token expires
// should trigger a single /auth/refresh, not one per request.
function refreshSession(): Promise<boolean> {
  refreshInFlight ??= fetch(`${API_PREFIX}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  })
    .then((res) => res.ok)
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

async function send(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  return fetch(`${API_PREFIX}${path}`, { ...init, headers, credentials: "include" });
}

const AUTH_PATHS = ["/auth/login", "/auth/refresh", "/auth/logout"];

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res = await send(path, init);
  if (res.status === 401 && !AUTH_PATHS.some((p) => path.startsWith(p))) {
    if (await refreshSession()) res = await send(path, init);
  }
  if (!res.ok) throw new ApiError(await toProblem(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiFetchBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  let res = await send(path, init);
  if (res.status === 401 && !AUTH_PATHS.some((p) => path.startsWith(p))) {
    if (await refreshSession()) res = await send(path, init);
  }
  if (!res.ok) throw new ApiError(await toProblem(res));
  return res.blob();
}
