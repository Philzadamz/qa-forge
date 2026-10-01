/**
 * Server-only fetch helper for React Server Components. Next's rewrites() only apply to
 * incoming HTTP requests, not to fetches issued from within the server process, so server
 * components must call the API directly and forward the caller's cookies by hand.
 */
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  staff_id: string | null;
  role: "admin" | "user" | "viewer";
  is_active: boolean;
}

export async function fetchServer(path: string, init: RequestInit = {}): Promise<Response> {
  const cookieStore = await cookies();
  const headers = new Headers(init.headers);
  headers.set("cookie", cookieStore.toString());
  return fetch(`${API_URL}/api/v1${path}`, { ...init, headers, cache: "no-store" });
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const res = await fetchServer("/auth/me");
  if (!res.ok) return null;
  return (await res.json()) as CurrentUser;
}

export async function requireUser(): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return user;
}

export async function requireAdmin(): Promise<CurrentUser> {
  const user = await requireUser();
  if (user.role !== "admin") redirect("/dashboard");
  return user;
}
