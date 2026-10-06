import { NextResponse, type NextRequest } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const ACCESS_COOKIE = "qa_forge_access";
const REFRESH_COOKIE = "qa_forge_refresh";
const REFRESH_MARGIN_MS = 30_000;

function accessTokenNeedsRefresh(token: string | undefined): boolean {
  if (!token) return true;
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))) as {
      exp?: number;
    };
    return typeof payload.exp !== "number" || payload.exp * 1000 - Date.now() < REFRESH_MARGIN_MS;
  } catch {
    return true;
  }
}

// Page navigations after the 15-minute access token expires would otherwise land on /login
// even though the refresh cookie is still valid. Refresh here, and pass the new cookies to this
// request too so the server components rendering it see the signed-in user.
export async function middleware(req: NextRequest) {
  const refresh = req.cookies.get(REFRESH_COOKIE)?.value;
  if (!refresh || !accessTokenNeedsRefresh(req.cookies.get(ACCESS_COOKIE)?.value)) {
    return NextResponse.next();
  }

  const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { cookie: `${REFRESH_COOKIE}=${refresh}` },
    cache: "no-store",
  });
  if (!res.ok) return NextResponse.next();

  const setCookies = res.headers.getSetCookie();
  const fresh = new Map<string, string>();
  for (const line of setCookies) {
    const pair = line.split(";")[0];
    const eq = pair.indexOf("=");
    fresh.set(pair.slice(0, eq), pair.slice(eq + 1));
  }
  const cookieHeader = [
    ...req.cookies
      .getAll()
      .filter((c) => !fresh.has(c.name))
      .map((c) => `${c.name}=${c.value}`),
    ...[...fresh].map(([name, value]) => `${name}=${value}`),
  ].join("; ");

  const headers = new Headers(req.headers);
  headers.set("cookie", cookieHeader);
  const next = NextResponse.next({ request: { headers } });
  for (const line of setCookies) next.headers.append("set-cookie", line);
  return next;
}

export const config = {
  matcher: ["/((?!api|_next/|favicon.ico|login|forgot-password|reset-password).*)"],
};
