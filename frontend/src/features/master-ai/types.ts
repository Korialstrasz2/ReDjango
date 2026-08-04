import type { AIAgentSummary, AIConversationBubble, AIExecutionRun, AIHistoryEntry, AIWorkspaceData } from "../../lib/types";

export type MasterAIAgent = AIAgentSummary & {
  mode?: "read_only" | "proposer";
  canProposeChanges?: boolean;
};

export type MasterAIWorkspaceData = Omit<AIWorkspaceData, "agents" | "activeRun"> & {
  agents: MasterAIAgent[];
  activeRun: MasterAIExecutionRun | null;
};

export type AIChangeFieldKind =
  | "text" | "longText" | "integer" | "number" | "boolean" | "choice"
  | "relation" | "multiRelation" | "image" | "color" | "structured";

export type AIChangeChoice = { value: string | number | boolean | null; label: string };

export type AIChangeField = {
  name: string;
  label: string;
  kind: AIChangeFieldKind | string;
  group: string;
  required: boolean;
  nullable: boolean;
  readOnly: boolean;
  help: string;
  choices: AIChangeChoice[];
  ui: {
    widget?: string;
    width?: "half" | "full" | string;
    minimum?: number;
    maximum?: number;
    step?: number;
    [key: string]: unknown;
  };
};

export type AIChangeProblem = { code: string; message: string; field?: string; operationId?: number };
export type AIChangeDiff = { field: string; label: string; before: unknown; after: unknown; changed: boolean };

export type AIChangeOperation = {
  id: number;
  position: number;
  entityType: "item" | "skill" | "spell" | "theme" | string;
  entityLabel: string;
  action: "create" | "update" | "archive";
  targetId: number | null;
  sourceId: number | null;
  displayLabel: string;
  selected: boolean;
  status: "proposed" | "valid" | "invalid" | "applied" | "skipped";
  original: { id?: number; label?: string; values?: Record<string, unknown>; display?: Record<string, unknown> };
  proposedValues: Record<string, unknown>;
  editedValues: Record<string, unknown>;
  effectiveValues: Record<string, unknown>;
  fields: AIChangeField[];
  diff: AIChangeDiff[];
  errors: AIChangeProblem[];
  warnings: AIChangeProblem[];
  result: { id?: number; label?: string; action?: string; entityType?: string };
  baseUpdatedAt: string | null;
  baseDigest: string;
};

export type AIChangeSet = {
  id: string;
  title: string;
  status: "draft" | "ready" | "applied" | "discarded" | "expired";
  revision: number;
  requestText: string;
  context: Record<string, unknown>;
  conversationId: number | null;
  agentId: number | null;
  canEdit: boolean;
  canValidate: boolean;
  canApply: boolean;
  canDiscard: boolean;
  validation: {
    token: string;
    validatedAt: string | null;
    summary: { selectedCount?: number; errorCount?: number; warningCount?: number };
    errors: AIChangeProblem[];
    warnings: AIChangeProblem[];
  };
  appliedBy: number | null;
  appliedAt: string | null;
  discardedAt: string | null;
  expiresAt: string | null;
  createdAt: string | null;
  updatedAt: string | null;
  operations: AIChangeOperation[];
};

export type MasterAIChatResult = {
  reply: string;
  history: AIHistoryEntry[];
  toolTrace: Array<{ name: string; arguments: Record<string, unknown>; isError: boolean }>;
  usage: { inputTokens: number; outputTokens: number };
  stopReason: string;
  runId: string;
  provider: { id: number; name: string; model: string };
  agent: { id: number; name: string };
  changeSet?: AIChangeSet;
};

export type MasterAIExecutionRun = Omit<AIExecutionRun, "result"> & {
  result: MasterAIChatResult | Record<string, never>;
};

export type MasterAIConversationState = {
  history: AIHistoryEntry[];
  bubbles: AIConversationBubble[];
  conversationId: number | null;
};
