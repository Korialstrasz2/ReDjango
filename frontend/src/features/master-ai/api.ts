import { apiRequest, getData, requestId } from "../../lib/api";
import type { AIExecutionRun, AIHistoryEntry } from "../../lib/types";
import type { AIChangeSet, AIChangeSetSummary, MasterAIExecutionRun } from "./types";

const actionRequest = <T>(path: string, method: "POST" | "PATCH" | "DELETE", action: string, payload: Record<string, unknown> = {}) => {
  const id = requestId();
  return apiRequest<T>(path, {
    method,
    headers: { "X-ReDjango-Action": action, "X-ReDjango-Request-Id": id },
    body: method === "DELETE" && !Object.keys(payload).length ? undefined : JSON.stringify({
      action,
      requestId: id,
      context: { screen: "master-ai" },
      payload,
      meta: { clientVersion: "react-v1" },
    }),
  });
};

export const getAIChangeSets = () => getData<{ changeSets: AIChangeSetSummary[] }>("/api/ai/change-sets/");
export const getAIChangeSet = (id: string) => getData<{ changeSet: AIChangeSet }>(`/api/ai/change-sets/${id}/`);
export const createAIChangeSet = (payload: Record<string, unknown>) => actionRequest<{ changeSet: AIChangeSet }>("/api/ai/change-sets/", "POST", "ai.changeSet.create", payload);
export const updateAIChangeSet = (id: string, payload: Record<string, unknown>) => actionRequest<{ changeSet: AIChangeSet }>(`/api/ai/change-sets/${id}/`, "PATCH", "ai.changeSet.update", payload);
export const discardAIChangeSet = (id: string) => actionRequest<{ changeSet: AIChangeSet }>(`/api/ai/change-sets/${id}/`, "DELETE", "ai.changeSet.discard");
export const addAIChangeOperation = (id: string, payload: Record<string, unknown>) => actionRequest<{ changeSet: AIChangeSet; operationId: number }>(`/api/ai/change-sets/${id}/operations/`, "POST", "ai.changeOperation.add", payload);
export const updateAIChangeOperation = (setId: string, operationId: number, payload: Record<string, unknown>) => actionRequest<{ changeSet: AIChangeSet }>(`/api/ai/change-sets/${setId}/operations/${operationId}/`, "PATCH", "ai.changeOperation.update", payload);
export const removeAIChangeOperation = (setId: string, operationId: number) => actionRequest<{ changeSet: AIChangeSet }>(`/api/ai/change-sets/${setId}/operations/${operationId}/`, "DELETE", "ai.changeOperation.remove");
export const validateAIChangeSet = (id: string) => actionRequest<{ changeSet: AIChangeSet }>(`/api/ai/change-sets/${id}/validate/`, "POST", "ai.changeSet.validate");
export const applyAIChangeSet = (id: string, token: string) => actionRequest<{ changeSet: AIChangeSet }>(`/api/ai/change-sets/${id}/apply/`, "POST", "ai.changeSet.apply", { token });
export const getAIChangeEntities = () => getData<{ entities: Array<Record<string, unknown>> }>("/api/ai/change-entities/");
export const searchAIChangeEntities = (type: string, query: string, limit = 20) => getData<{ results: Array<Record<string, unknown>> }>(`/api/ai/change-entities/${encodeURIComponent(type)}/search/?q=${encodeURIComponent(query)}&limit=${limit}`);

export function askMasterAssistant(payload: {
  message: string;
  history: AIHistoryEntry[];
  agentId: number;
  conversationId?: number;
  changeSetId?: string;
  context?: { entityType?: string; targetId?: number; sourceSurface?: string };
}) {
  const id = requestId();
  return apiRequest<{ run: MasterAIExecutionRun }>("/api/ai/", {
    method: "POST",
    headers: { "X-ReDjango-Action": "ai.ask", "X-ReDjango-Request-Id": id },
    body: JSON.stringify({ action: "ai.ask", requestId: id, context: { screen: "master-ai" }, payload, meta: { clientVersion: "react-v1" } }),
  });
}

export const getMasterAIExecutionRun = async (runId: string) => {
  const response = await apiRequest<{ run: AIExecutionRun }>(`/api/ai/runs/${runId}/`);
  return { ...response, data: { run: response.data.run as MasterAIExecutionRun } };
};

export const cancelMasterAIExecutionRun = (runId: string) => actionRequest<{ run: MasterAIExecutionRun }>(`/api/ai/runs/${runId}/`, "DELETE", "ai.cancel");
