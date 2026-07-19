import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchWithTimeout, formatApiDetail } from "./api";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("fetchWithTimeout", () => {
  it("interrompt un appel REST figé avec une erreur lisible", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted")));
          }),
      ),
    );

    const call = fetchWithTimeout("http://api.test/slow", {}, 25);
    const assertion = expect(call).rejects.toEqual(
      new ApiError(408, "L’API met trop de temps à répondre — réessaie."),
    );
    await vi.advanceTimersByTimeAsync(25);
    await assertion;
  });
});

describe("formatApiDetail", () => {
  it("rend les erreurs de validation FastAPI lisibles", () => {
    expect(
      formatApiDetail([
        { type: "missing", loc: ["body", "model_cast", "models"], msg: "Field required" },
      ]),
    ).toBe("model_cast → models : Field required");
  });

  it("n'affiche jamais la conversion implicite d'un objet", () => {
    expect(formatApiDetail({ message: "Casting indisponible" })).toBe("Casting indisponible");
    expect(formatApiDetail({ code: "invalid_cast" })).not.toBe("[object Object]");
  });
});
