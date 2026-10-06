import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, apiFetchBlob } from "./api";

afterEach(() => vi.restoreAllMocks());

describe("apiFetch", () => {
  it("prefixes the path and returns JSON", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    await expect(apiFetch("/health")).resolves.toEqual({ status: "ok" });
    expect(spy.mock.calls[0][0]).toBe("/api/v1/health");
  });

  it("throws ApiError carrying the problem+json body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ title: "Unauthorized", status: 401, detail: "Bad creds" }), {
        status: 401,
        headers: { "content-type": "application/problem+json" },
      }),
    );
    const err = await apiFetch("/auth/login", { method: "POST" }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(401);
    expect((err as ApiError).message).toBe("Bad creds");
  });

  it("falls back to status text for non-JSON errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("boom", { status: 502, statusText: "Bad Gateway" }),
    );
    const err = (await apiFetch("/x").catch((e: unknown) => e)) as ApiError;
    expect(err.problem).toEqual({ title: "Bad Gateway", status: 502 });
  });
});

describe("session refresh", () => {
  it("refreshes once after a 401 and retries the original request", async () => {
    const calls: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      calls.push(url);
      if (url.endsWith("/auth/refresh")) return new Response(null, { status: 200 });
      if (calls.filter((c) => c.endsWith("/suites/s1/reports/draft")).length === 1) {
        return new Response(JSON.stringify({ title: "Unauthorized", status: 401 }), {
          status: 401,
          headers: { "content-type": "application/problem+json" },
        });
      }
      return new Response(JSON.stringify({ id: "r1" }), { status: 201 });
    });

    await expect(apiFetch("/suites/s1/reports/draft", { method: "POST" })).resolves.toEqual({
      id: "r1",
    });
    expect(calls).toEqual([
      "/api/v1/suites/s1/reports/draft",
      "/api/v1/auth/refresh",
      "/api/v1/suites/s1/reports/draft",
    ]);
  });

  it("shares one refresh across concurrent 401s", async () => {
    let refreshes = 0;
    let suiteCalls = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) {
        refreshes += 1;
        return new Response(null, { status: 200 });
      }
      suiteCalls += 1;
      if (suiteCalls <= 2) return new Response("{}", { status: 401 });
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });

    await Promise.all([apiFetch("/a"), apiFetch("/b")]);
    expect(refreshes).toBe(1);
  });

  it("does not try to refresh the refresh call itself", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}", { status: 401 }));
    await apiFetch("/auth/login", { method: "POST" }).catch(() => undefined);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("returns the blob for file downloads after refreshing", async () => {
    let first = true;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input).endsWith("/auth/refresh")) return new Response(null, { status: 200 });
      if (first) {
        first = false;
        return new Response("{}", { status: 401 });
      }
      return new Response("xlsx-bytes", { status: 200 });
    });
    const blob = await apiFetchBlob("/suites/s1/export/xlsx", { method: "POST" });
    expect(await blob.text()).toBe("xlsx-bytes");
  });
});
