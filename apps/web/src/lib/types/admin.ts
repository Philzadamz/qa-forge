export interface TestCaseType {
  id: string;
  name: string;
  description: string | null;
  id_prefix_hint: string | null;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DefaultTestCase {
  id: string;
  type_id: string;
  feature: string;
  scenario: string;
  steps: string[];
  expected_result: string;
  default_actual_result: string;
  evidence_group: string;
  tags: string[];
  sort_order: number;
  is_active: boolean;
  version: number;
}

export type Role = "admin" | "user" | "viewer";

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  staff_id: string | null;
  role: Role;
  auth_provider: string;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface ImportWarning {
  row: number | null;
  message: string;
}

export interface ImportPreviewCase {
  feature: string;
  scenario: string;
  steps: string[];
  expected_result: string;
  default_actual_result: string;
  evidence_group: string;
  sort_order: number;
}

export interface ImportPreview {
  cases: ImportPreviewCase[];
  warnings: ImportWarning[];
}
