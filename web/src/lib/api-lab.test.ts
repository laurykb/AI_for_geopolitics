import { afterEach, describe, expect, it, vi } from "vitest";

import { getLab } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getLab", () => {
  it("utilise le contrat campagne lorsqu'un backend ancien ne connaît pas /api/lab", async () => {
    const lab = { title: "Laboratoire compatible", protocols: [] };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Not Found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ title: "Campagne", chapters: [], lab }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getLab()).resolves.toEqual(lab);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/lab");
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain("/api/campaign");
  });
});
