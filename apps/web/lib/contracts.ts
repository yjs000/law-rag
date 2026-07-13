export type Citation = {
  id: string;
  provision_id?: string;
  document_title: string;
  version_label: string;
  path: string;
  quote: string;
  source_url: string;
};

export type ChecklistItem = {
  label: string;
  status: string;
  citation_ids: string[];
};

export type QuestionResponse = {
  request_id?: string;
  mode: "ai" | "search_only";
  summary: string;
  scope: string;
  sections: { claim: string; explanation: string; citation_ids: string[] }[];
  checklist: ChecklistItem[];
  citations: Citation[];
  limitations: string[];
  corpus_as_of?: string | null;
};

export type CorpusStatus = {
  last_successful_sync: string | null;
  ai_available: boolean;
  warnings: string[];
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
};

export type QuestionInput = {
  question: string;
  as_of_date: string;
  project_stage: string;
};
