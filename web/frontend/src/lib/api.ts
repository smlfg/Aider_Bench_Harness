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

export async function judgeRun(runId: string): Promise<{ run_id: string; status: string; judge_score: number | null }> {
  const resp = await fetch(`/api/runs/${runId}/judge`, { method: 'POST' });
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || `Judge failed for ${runId}`);
  }
  return resp.json();
}

export interface ExperimentPlan {
  exp_id: string;
  task_ids: string[];
  base_md: string;
  target_md: string;
  parts: number;
  reps_per_part: number;
  parallel: number;
  conditions: { condition_id: string; md_path: string; sections: number }[];
  total_sections: number;
  total_runs: number;
  status: string;
}

export interface ExperimentStatus {
  exp_id: string;
  status: string;
  total_runs: number;
  completed: number;
  success: number;
  failed: number;
  running: number;
  conditions: {
    condition_id: string;
    sections: number;
    total: number;
    completed: number;
    success: number;
    failed: number;
    running: number;
    avg_judge_score: number | null;
    avg_duration: number | null;
  }[];
  errors: { run_id: string; error: string }[];
}

export async function createExperiment(data: {
  task_ids: string[];
  base_md?: string;
  target_md?: string;
  parts?: number;
  reps_per_part?: number;
  parallel?: number;
}): Promise<ExperimentPlan> {
  const resp = await fetch('/api/experiment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || 'Failed to create experiment');
  }
  return resp.json();
}

export async function startExperiment(expId: string): Promise<{ launched: number; errors: number; run_ids: string[] }> {
  const resp = await fetch(`/api/experiment/${expId}/start`, { method: 'POST' });
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || 'Failed to start experiment');
  }
  return resp.json();
}

export async function fetchExperimentStatus(expId: string): Promise<ExperimentStatus> {
  const resp = await fetch(`/api/experiment/${expId}`);
  return resp.json();
}

export async function fetchExperiments(): Promise<ExperimentPlan[]> {
  const resp = await fetch('/api/experiments');
  return resp.json();
}

export interface IncrementalPlan {
  exp_id: string;
  task_id: string;
  base_md: string;
  increment_md: string;
  repetitions: number;
  parallel: number;
  total_lines: number;
  variants: {
    condition_id: string;
    k: number;
    lines_count: number;
    md_path: string;
    repetitions: { run_id: string; condition_id: string; artifacts_dir: string; k: number; rep: number; status: string }[];
  }[];
  total_runs: number;
  status: string;
}

export interface IncrementalStatus {
  exp_id: string;
  status: string;
  task_id: string;
  total_lines: number;
  total_runs: number;
  completed: number;
  success: number;
  failed: number;
  running: number;
  pending: number;
  variants_k: {
    k: number;
    condition_id: string;
    lines_count: number;
    runs_completed: number;
    runs_success: number;
    judge_score_mean: number | null;
    judge_score_std: number | null;
    duration_mean: number | null;
  }[];
}

export async function createIncremental(data: {
  task_id: string;
  base_md?: string;
  increment_md?: string;
  repetitions?: number;
  iteration?: number;
  parallel?: number;
}): Promise<IncrementalPlan> {
  const resp = await fetch('/api/incremental', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || 'Failed to create incremental experiment');
  }
  return resp.json();
}

export async function launchIncremental(expId: string): Promise<{ launched: number; errors: number; run_ids: string[] }> {
  const resp = await fetch(`/api/incremental/${expId}/launch`, { method: 'POST' });
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || 'Failed to launch incremental experiment');
  }
  return resp.json();
}

export async function fetchIncrementalStatus(expId: string): Promise<IncrementalStatus> {
  const resp = await fetch(`/api/incremental/${expId}`);
  return resp.json();
}
