import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "./api";

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
