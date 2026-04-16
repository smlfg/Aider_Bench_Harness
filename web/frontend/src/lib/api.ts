export interface Run {
  run_id: string;
  task_id: string;
  condition_id: string;
  iteration: number;
  model_name: string;
  start_ts: string;
  end_ts: string | null;
  duration_seconds: number | null;
  task_success: boolean | null;
  tests_passed: number | null;
  tests_total: number | null;
  lines_added: number | null;
  lines_removed: number | null;
  files_changed: number | null;
  judge_score: number | null;
  infrastructure_error: boolean;
  failure_kind: string | null;
  error_detail: string | null;
  conventions_content?: string;
  conventions_mutation_note?: string;
}

export interface AnalysisRow {
  iteration: number;
  condition: string;
  metric: string;
  n: number;
  point_estimate: number;
  ci_low: number | null;
  ci_high: number | null;
  method: string;
}

export interface ComparisonRow {
  iteration: number;
  metric: string;
  baseline_estimate: number;
  candidate_estimate: number;
  delta: number;
  test_name: string;
  p_value: number | null;
  effect_size: number | null;
  composite: number | null;
}

export interface TrajectoryRow {
  iteration: number;
  conventions_hash: string;
  mutation_note: string;
  cumulative_success_rate: number;
  cumulative_diff_size_loc_mean: number;
  pareto_dominated: number;
}

export interface Task {
  instance_id: string;
  task_id?: string;
  repo: string;
  problem_statement: string;
  FAIL_TO_PASS: string;
  PASS_TO_PASS: string;
}

export interface Convention {
  name: string;
  path: string;
  hash: string;
  content: string;
}

export async function fetchRuns(iteration?: number, condition?: string): Promise<Run[]> {
  const params = new URLSearchParams();
  if (iteration !== undefined) params.append('iteration', iteration.toString());
  if (condition !== undefined) params.append('condition', condition);
  const resp = await fetch(`/api/runs?${params.toString()}`);
  return resp.json();
}

export async function fetchRunDetail(runId: string): Promise<Run & { [key: string]: any }> {
  const resp = await fetch(`/api/runs/${runId}`);
  return resp.json();
}

export async function fetchAnalysis(iteration?: number): Promise<AnalysisRow[]> {
  const params = new URLSearchParams();
  if (iteration !== undefined) params.append('iteration', iteration.toString());
  const resp = await fetch(`/api/analysis?${params.toString()}`);
  return resp.json();
}

export async function fetchComparisons(iteration?: number): Promise<ComparisonRow[]> {
  const params = new URLSearchParams();
  if (iteration !== undefined) params.append('iteration', iteration.toString());
  const resp = await fetch(`/api/comparisons?${params.toString()}`);
  return resp.json();
}

export async function fetchTrajectory(): Promise<TrajectoryRow[]> {
  const resp = await fetch('/api/trajectory');
  return resp.json();
}

export async function fetchTasks(): Promise<Task[]> {
  const resp = await fetch('/api/tasks');
  return resp.json();
}

export async function fetchConventions(): Promise<Convention[]> {
  const resp = await fetch('/api/conventions');
  return resp.json();
}

export async function launchRun(data: {
  task_id: string;
  condition: string;
  iteration: number;
  run_index: number;
  conventions_path?: string;
}): Promise<{ run_id: string; status: string }> {
  const resp = await fetch('/api/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || 'Failed to launch run');
  }
  return resp.json();
}

export async function abortRun(runId: string): Promise<void> {
  await fetch(`/api/runs/${runId}/abort`, { method: 'POST' });
}
