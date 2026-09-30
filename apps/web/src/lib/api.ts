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

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const res = await fetch(`${API_PREFIX}${path}`, { ...init, headers, credentials: "include" });
  if (!res.ok) throw new ApiError(await toProblem(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
