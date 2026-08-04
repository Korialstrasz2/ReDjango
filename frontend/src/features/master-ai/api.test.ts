import { afterEach, describe, expect, it, vi } from "vitest";
import { applyAIChangeSet, askMasterAssistant, discardAIChangeSet, updateAIChangeOperation } from "./api";

const okEnvelope = (data: unknown) => ({ ok: true, requestId: "server", data, events: [], warnings: [], errors: [] });

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
});

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

  it("passes only the parsed safe launcher context to proposer chat", async () => {
    window.history.replaceState({}, "", "/tools/master-ai?entity=spell&source=17&surface=skill-management&label=Tocco&prompt=Crea");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(okEnvelope({ run: { id: "run-1" } })), { status: 200, headers: { "Content-Type": "application/json" } }));
    await askMasterAssistant({ message: "Crea", history: [], agentId: 4 });
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/ai/");
    const body = JSON.parse(String(init?.body));
    expect(body.payload.context).toEqual({ entityType: "spell", sourceId: 17, sourceSurface: "skill-management" });
    expect(body.payload.context).not.toHaveProperty("label");
  });

  it("lets an explicit safe context override the current URL", async () => {
    window.history.replaceState({}, "", "/tools/master-ai?entity=item&target=2&surface=item-management");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(okEnvelope({ run: { id: "run-2" } })), { status: 200, headers: { "Content-Type": "application/json" } }));
    await askMasterAssistant({
      message: "Aggiorna",
      history: [],
      agentId: 4,
      context: { entityType: "skill", targetId: 8, sourceSurface: "skill-management" },
    });
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.payload.context).toEqual({ entityType: "skill", targetId: 8, sourceSurface: "skill-management" });
  });
});