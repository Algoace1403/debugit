// ── GitHub User ──────────────────────────────────────────────────

export interface GitHubUser {
  login: string;
  name: string;
  avatar_url: string;
  github_id: string;
}

// ── Backend results.json schema ──────────────────────────────────

export interface FixEntry {
  file: string;
  bug_type: BugType;
  line_number: number;
  issue_line: string;
  commit_message: string;
  status: "fixed" | "failed";
  iteration: number;
  diff: string;
}

export interface CIRunEntry {
  iteration: number;
  status: "PASSED" | "FAILED";
  mode: "CI" | "LOCAL_ONLY";
  run_url: string;
  timestamp: string;
  failures_remaining: number;
}

export interface ScoreBreakdown {
  base: number;
  speed_bonus: number;
  efficiency_penalty: number;
  total: number;
}

export interface Results {
  repo_url: string;
  team_name: string;
  leader_name: string;
  branch_name: string;
  start_time: string;
  end_time: string | null;
  total_time_seconds: number;
  total_failures_detected: number;
  total_fixes_applied: number;
  total_commits: number;
  final_status: "PASSED" | "FAILED";
  score: ScoreBreakdown;
  fixes: FixEntry[];
  ci_runs: CIRunEntry[];
}

// ── WebSocket event ─────────────────────────────────────────────

export interface WSEvent {
  event_type: "node_start" | "node_end" | "progress" | "error" | "complete";
  run_id: string;
  node: string | null;
  message: string;
  data: Record<string, unknown> | null;
  timestamp: string;
}

// ── API responses ───────────────────────────────────────────────

export interface HealResponse {
  run_id: string;
  status: string;
}

export interface RunStatus {
  run_id: string;
  status: string;
  current_node: string;
  iteration: number;
  max_iterations: number;
  error: string | null;
  results: Results | null;
}

// ── Enum helpers ────────────────────────────────────────────────

export type BugType =
  | "LINTING"
  | "SYNTAX"
  | "LOGIC"
  | "TYPE_ERROR"
  | "IMPORT"
  | "INDENTATION";

export const BUG_TYPE_COLORS: Record<BugType, string> = {
  LINTING: "bg-blue-100 text-blue-800",
  SYNTAX: "bg-orange-100 text-orange-800",
  LOGIC: "bg-purple-100 text-purple-800",
  TYPE_ERROR: "bg-red-100 text-red-800",
  IMPORT: "bg-yellow-100 text-yellow-800",
  INDENTATION: "bg-teal-100 text-teal-800",
};

export const NODE_LABELS: Record<string, string> = {
  repo_analyzer: "Analyzing Repository",
  test_runner: "Running Tests",
  bug_classifier: "Classifying Bugs",
  fix_generator: "Generating Fixes",
  fix_validator: "Validating Fixes",
  git_ops: "Committing Changes",
  ci_monitor: "Monitoring CI/CD",
  scorer: "Calculating Score",
};
