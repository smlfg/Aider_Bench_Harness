export interface PreflightCheck {
  label: string;
  ok: boolean;
  detail: string;
}

export interface PreflightResult {
  docker: PreflightCheck;
  swebench: PreflightCheck;
  datasets: PreflightCheck;
  aider: PreflightCheck;
  apikey: PreflightCheck;
  litellm: PreflightCheck;
}

export async function fetchPreflight(): Promise<PreflightResult> {
  const resp = await fetch('/api/preflight');
  if (!resp.ok) throw new Error('Preflight check failed');
  return resp.json();
}