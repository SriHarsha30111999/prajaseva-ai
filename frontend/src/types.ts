import type { AppRow } from "./pages/Applications";

export type AILog = {
  id: number; kind: string; mode: "live" | "demo"; model: string; output: any; requested_by: string; created_at: string;
};

export type Doc = { id: number; doc_type: string; filename: string; content_text: string; uploaded_at: string };

export type Report = {
  id: number; observations: Record<string, string>; report_text: string; ai_mode: string | null;
  submitted_by: string; submitted_at: string;
};

export type Detail = AppRow & {
  guardian_name: string; age: number; gender: string; district: string; address: string; occupation: string;
  household_members: number; archived?: boolean; field_verification_required: boolean | null;
  documents: Doc[]; reports: Report[];
  history: { id: number; action: string; user_name: string; role: string; remarks: string; previous_status: string | null; new_status: string | null; created_at: string }[];
  analysis: AILog | null; summary: AILog | null;
  required_documents: string[]; available_actions: string[];
};

export type PanelProps = { app: Detail; setApp: (d: Detail) => void; reload: () => void };
