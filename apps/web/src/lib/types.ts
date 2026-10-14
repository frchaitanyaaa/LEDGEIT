export type Role = "OPERATOR" | "QUALITY_ENGINEER" | "QUALITY_MANAGER" | "AUDITOR" | "ADMIN";
export type Decision = "PASS" | "FAIL";
export type CheckStatus = "PASS" | "FAIL" | "PENDING";
export type VerifyResult = "VERIFIED" | "FAILED" | "PENDING_ANCHOR";

export interface User {
  id: string;
  employee_code: string;
  full_name: string;
  email: string;
  role: Role;
  public_key: string | null;
  public_keys: { public_key: string; label: string | null; created_at: string }[];
}

export interface InspectionRow {
  id: string;
  inspection_code: string;
  unit_serial: string;
  batch_code: string;
  line: string;
  device: string;
  decision: Decision;
  defect_class: string | null;
  severity: string;
  confidence: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  record_hash: string;
  inspected_at: string;
  model_name: string;
  model_version: string;
  status: string;
  final_decision: Decision | null;
  anchor_status: string;
  last_verification: VerifyResult | null;
}

export interface Box { x1: number; y1: number; x2: number; y2: number; cls: string; conf: string }

export interface InspectionDetail extends InspectionRow {
  record: Record<string, any>;
  device_signature: string;
  device_public_key: string;
  explanation: { method: string; summary: string; heatmap_sha256: string | null; boxes: Box[] };
  risk_reasons: string[];
  model: { id: string; name: string; version: string; weights_sha256: string; status: string; framework: string;
           dataset_version: string; approved_at: string | null };
  product: { sku: string; name: string; is_regulated: boolean };
  evidence: { id: string; kind: "IMAGE" | "HEATMAP"; sha256: string; phash: string | null; mime_type: string;
              size_bytes: number; width: number; height: number; url: string }[];
  overrides: any[];
  alerts: any[];
  latest_verification: { id: string; result: VerifyResult; checks: Record<string, CheckOut>; verified_at: string } | null;
}

export interface CheckOut { status: CheckStatus; title: string; problems: string[]; facts: Record<string, any> }

export interface VerifyOut {
  inspection_id: string;
  inspection_code: string;
  result: VerifyResult;
  message: string;
  checks: Record<string, CheckOut>;
  verified_at?: string;
}

export interface TimelineEvent {
  id: number;
  seq: number;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  payload: any;
  payload_hash: string;
  prev_event_hash: string;
  event_hash: string;
  signature: string | null;
  created_at: string;
  queued_risk: string | null;
  anchor: null | { batch_id: number; merkle_root: string; status: string; leaf_index: number; tx_hash: string | null;
                   network: string | null; block_number: number | null };
}
