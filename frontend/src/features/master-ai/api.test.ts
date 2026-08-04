import { afterEach, describe, expect, it, vi } from "vitest";
import { applyAIChangeSet, discardAIChangeSet, updateAIChangeOperation } from "./api";

const okEnvelope = (data: unknown) => ({ ok: true, requestId: "server", data, events: [], warnings: [], errors: [] });

afterEach(() => vi.restoreAllMocks());

describe("Master AI API", () => {
  it("sends human apply with the validation token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(okEnvelope({ changeSet: { id: "set-1" } })), { status: 200, headers: { "Content-Type": "application/json" } }));
    await applyAIChangeSet("set-1", "signed-token");
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/ai/change-sets/set-1/apply/");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body)).payload).toEqual({ token: "signed-token" });
    expect(new Headers(init?.headers).get("X-ReDjango-Action")).toBe("ai.changeSet.apply");
  });

  it("discards without calling the apply route", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(okEnvelope({ changeSet: { id: "set-2" } })), { status: 200, headers: { "Content-Type": "application/json" } }));
    await discardAIChangeSet("set-2");
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/ai/change-sets/set-2/");
    expect(init?.method).toBe("DELETE");
    expect(String(path)).not.toContain("apply");
  });

  it("patches only the explicit operation draft payload", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(okEnvelope({ changeSet: { id: "set-3" } })), { status: 200, headers: { "Content-Type": "application/json" } }));
    await updateAIChangeOperation("set-3", 7, { editedValues: { name: "Tocco mortale" } });
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/ai/change-sets/set-3/operations/7/");
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(String(init?.body)).payload).toEqual({ editedValues: { name: "Tocco mortale" } });
  });
});
