export interface User {
  id: string;
  email: string;
  full_name: string;
  active_organization_id: string | null;
}

export interface Organization {
  id: string;
  name: string;
  created_at: string;
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
}

export interface Invitation {
  id: string;
  email: string;
  role: string;
  status: string;
  created_at: string;
}

export interface Integration {
  id: string;
  provider: string;
  external_account_id: string | null;
  connection_status: string;
  last_synced_at: string | null;
  last_error: string | null;
  permissions: string[];
}

export interface Lead {
  id: string;
  external_id: string | null;
  name: string;
  email: string | null;
  company: string | null;
  deal_value: number;
  stage: string;
  owner: string | null;
  last_activity_at: string | null;
  days_inactive: number | null;
  priority: string | null;
  notes: string | null;
  source_provider: string | null;
  created_at: string;
  updated_at: string;
}

export interface Finding {
  id: string;
  lead_id: string;
  type: string;
  priority: string;
  title: string;
  description: string;
  evidence: unknown[];
  created_at: string;
}

export interface Recommendation {
  id: string;
  lead_id: string;
  priority: string;
  explanation: string;
  evidence: unknown[];
  proposed_action: unknown;
  status: string;
  created_at: string;
  lead?: Lead;
}

export interface AgentEvent {
  id: string;
  step: string;
  status: string;
  message: string;
  metadata: unknown;
  created_at: string;
}

export interface Task {
  id: string;
  organization_id: string;
  initiated_by: string;
  user_request: string;
  task_type: string;
  status: string;
  intent: string | null;
  created_at: string;
  completed_at: string | null;
  error: string | null;
}

export interface TaskDetail extends Task {
  reasoning_summary?: string | null;
  data_sources?: unknown;
  result?: unknown;
  findings?: Finding[];
  recommendations?: Recommendation[];
  events?: AgentEvent[];
}

export interface ApprovalDetail {
  id: string;
  recommendation_id: string;
  status: string;
  approved_by: string | null;
  approved_at: string | null;
  expires_at: string | null;
  action_hash: string;
  risk_level: string;
  lead: Lead;
  recommendation: Recommendation;
  note?: string | null;
}

export interface Execution {
  id: string;
  organization_id: string;
  task_id: string | null;
  recommendation_id: string | null;
  integration_id: string | null;
  action_type: string;
  idempotency_key: string;
  status: string;
  request_payload: unknown;
  response_payload: unknown;
  error_message: string | null;
  executed_at: string | null;
}

export interface ActivityItem {
  id: string;
  type: string;
  title: string;
  status: string;
  actor: string;
  provider: string | null;
  timestamp: string;
  detail: unknown;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
  organization: Organization;
}

export interface DashboardOverview {
  metrics: {
    active_leads: number;
    pipeline_value: number;
    neglected_leads: number;
    overdue_followups: number;
    pending_approvals: number;
    completed_tasks: number;
  };
  needs_attention: Lead[];
  recent_activity: ActivityItem[];
  high_priority: Lead[];
  integration_health: Integration[];
}

export interface IntegrationConnectResponse {
  authorization_url: string;
  state: string;
  callback_url: string;
}

export interface LeadImportResponse {
  imported: number;
  updated: number;
  leads: Lead[];
}
