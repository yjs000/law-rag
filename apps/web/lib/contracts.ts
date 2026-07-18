export type Citation = {
  id: string;
  provision_id?: string;
  document_title: string;
  version_label: string;
  path: string;
  quote: string;
  source_url: string;
  source_kind?: "law" | "decree" | "rule" | "administrative_rule";
};

export type ChecklistItem = {
  label: string;
  status: string;
  citation_ids: string[];
};

export type QuestionResponse = {
  request_id?: string;
  mode: "ai" | "search_only";
  requested_answer_mode?: "terra" | "search_only";
  fallback_reason?: "ai_disabled" | "quota_exhausted" | "billing_or_quota_error" | "embedding_error" | "generation_error" | "grounding_failed" | "no_evidence" | null;
  result_status?: "results" | "no_results";
  no_results_reason?: string | null;
  summary: string;
  scope: string;
  sections: { claim: string; explanation: string; citation_ids: string[] }[];
  checklist: ChecklistItem[];
  citations: Citation[];
  limitations: string[];
  corpus_as_of?: string | null;
  conversation_id?: string | null;
};

export type CorpusStatus = {
  last_successful_sync: string | null;
  ai_available: boolean;
  ai_unavailable_reason?: "ai_disabled" | "quota_exhausted" | null;
  warnings: string[];
  items?: {
    title: string;
    source_kind: string;
    state: "ready" | "missing" | "failed";
    latest_effective_date?: string | null;
  }[];
};

export type MockUser = {
  id: string;
  email: string;
  display_name: string;
  auth_provider: "google";
  created_at: string;
};

export type QuestionHistoryItem = {
  id: string;
  user_id: string;
  request: QuestionInput;
  response: QuestionResponse;
  created_at: string;
  expires_at: string;
  conversation_id?: string | null;
  turn_index?: number | null;
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
  last_turn_id: string;
};

export type ConversationPage = {
  items: ConversationSummary[];
  next_cursor?: string | null;
  has_more: boolean;
};

export type ConversationTurnPage = {
  items: QuestionHistoryItem[];
  next_cursor?: string | null;
  has_more: boolean;
};

export type QuestionInput = {
  client_request_id?: string;
  question: string;
  as_of_date: string;
  project_stage: string;
  answer_mode?: "terra" | "search_only";
  conversation_id?: string;
  conversation_context?: Array<{ question: string; answer: string }>;
};
