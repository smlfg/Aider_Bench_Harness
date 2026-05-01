import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchRunDetail, abortRun } from '../lib/api';
import type { Run } from '../lib/api';
import type { Task } from '../lib/api';
import { Shield, FileText, Terminal, Code, StopCircle, Zap } from 'lucide-react';

interface TokensPayload {
  tokens_in: number;
  tokens_out: number;
}

interface PatchPayload {
  patch: string;
  files_changed: number;
  lines_added: number;
  lines_removed: number;
}

interface DonePayload {
  phase: string;
  exit_code?: number;
  task_success?: boolean;
  infrastructure_error?: boolean;
  tests_passed?: number;
  tests_total?: number;
}

const PHASE_LABELS: Record<string, string> = {
  starting:        'Starting',
  setup_repo:       'Cloning Repo',
  aider_running:    'Aider Running',
  aider_retry:      'Aider Retry',
  docker_eval:      'Evaluating',
  done:             'Done',
  error:            'Error',
};

const MonitorPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<Run | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [phase, setPhase] = useState<string>('initializing');
  const [logs, setLogs] = useState<string[]>([]);
  const [patch, setPatch] = useState<string>('');
  const [patchStats, setPatchStats] = useState({ files: 0, added: 0, removed: 0 });
  const [tokens, setTokens] = useState<TokensPayload | null>(null);
  const [isDone, setIsDone] = useState(false);
  const [events, setEvents] = useState<{ ts: string; type: string; msg: string }[]>([]);

  const logEndRef = useRef<HTMLDivElement>(null);

  const addEvent = (type: string, msg: string) => {
    const now = new Date();
    const ts = now.toLocaleTimeString('de-DE', { hour12: false });
    setEvents(prev => [...prev.slice(-99), { ts, type, msg }]);
  };

  useEffect(() => {
    if (!runId) return;

    fetchRunDetail(runId).then(data => {
      setRun(data);
      if (data.task_id) {
        fetch(`/api/tasks/${encodeURIComponent(data.task_id)}`)
          .then(r => r.ok ? r.json() : null)
          .then(t => setTask(t))
          .catch(() => {});
      }
    });

    const eventSource = new EventSource(`/api/runs/${runId}/stream`);

    eventSource.addEventListener('phase', (e) => {
      const data = JSON.parse(e.data);
      setPhase(data.phase);
      addEvent('phase', PHASE_LABELS[data.phase] || data.phase);
    });

    eventSource.addEventListener('log', (e) => {
      const data = JSON.parse(e.data);
      setLogs(prev => [...prev, data.line]);
    });

    eventSource.addEventListener('patch_changed', (e) => {
      const data: PatchPayload = JSON.parse(e.data);
      setPatch(data.patch || '');
      setPatchStats({
        files: data.files_changed,
        added: data.lines_added,
        removed: data.lines_removed,
      });
      addEvent('patch', `+${data.lines_added} -${data.lines_removed} (${data.files_changed} files)`);
    });

    eventSource.addEventListener('tokens', (e) => {
      const data: TokensPayload = JSON.parse(e.data);
      setTokens(data);
    });

    eventSource.addEventListener('done', (e) => {
      const data: DonePayload = JSON.parse(e.data);
      setIsDone(true);
      addEvent('done', `exit=${data.exit_code} success=${data.task_success} infra=${data.infrastructure_error}`);
      eventSource.close();
      setTimeout(() => navigate(`/debrief/${runId}`), 1500);
    });

    eventSource.onerror = () => {
      addEvent('error', 'SSE connection lost — retrying…');
    };

    return () => eventSource.close();
  }, [runId, navigate]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleAbort = async () => {
    if (runId && window.confirm('Abort this run?')) {
      await abortRun(runId);
      addEvent('abort', 'Abort requested');
    }
  };

  const formatTokens = (t: TokensPayload) => {
    const fmt = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
    return `↑${fmt(t.tokens_in)} ↓${fmt(t.tokens_out)}`;
  };

  if (!runId) return <div className="p-8 text-gray-500">Missing Run ID</div>;

  const phaseColor: Record<string, string> = {
    starting:       'bg-gray-100 text-gray-700',
    setup_repo:     'bg-yellow-100 text-yellow-800',
    aider_running:  'bg-blue-100 text-blue-800 animate-pulse',
    aider_retry:    'bg-orange-100 text-orange-800 animate-pulse',
    docker_eval:    'bg-purple-100 text-purple-800 animate-pulse',
    done:           'bg-green-100 text-green-800',
    error:          'bg-red-100 text-red-800',
  };

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col space-y-3">

      {/* ── Status Bar ── */}
      <div className="flex items-center justify-between bg-white p-3 rounded-lg shadow-sm border border-gray-200">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold text-gray-400 uppercase">Phase</span>
            <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${phaseColor[phase] || 'bg-gray-100 text-gray-700'}`}>
              {PHASE_LABELS[phase] || phase}
            </span>
          </div>
          <div className="h-4 w-px bg-gray-200" />
          <div className="font-mono text-xs text-gray-500">{runId}</div>
          {tokens && (
            <>
              <div className="h-4 w-px bg-gray-200" />
              <div className="flex items-center space-x-1 text-xs font-mono text-blue-600">
                <Zap size={12} />
                <span>{formatTokens(tokens)}</span>
              </div>
            </>
          )}
        </div>
        {!isDone && (
          <button
            onClick={handleAbort}
            className="flex items-center space-x-2 px-4 py-2 bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 transition-colors text-sm"
          >
            <StopCircle size={16} />
            <span>Abort</span>
          </button>
        )}
      </div>

      {/* ── 4-Quadrant Grid ── */}
      <div className="flex-1 grid grid-cols-2 gap-3 min-h-0">

        {/* Q1: Task Definition */}
        <div className="flex flex-col bg-white rounded-lg shadow-sm border border-gray-200 min-h-0">
          <div className="px-4 py-2 border-b border-gray-100 flex items-center space-x-2 bg-gray-50 rounded-t-lg">
            <FileText size={14} className="text-gray-500" />
            <h3 className="text-xs font-bold text-gray-600 uppercase tracking-wide">Task Definition</h3>
          </div>
          <div className="p-4 overflow-y-auto text-sm">
            <h4 className="font-mono font-bold text-gray-900 text-xs mb-2">{run?.task_id || task?.instance_id}</h4>
            <p className="text-gray-700 whitespace-pre-wrap font-sans leading-relaxed text-sm">
              {task?.problem_statement || 'Fetching task details…'}
            </p>
            {task?.FAIL_TO_PASS && (
              <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs">
                <span className="font-bold text-red-600">FAIL_TO_PASS: </span>
                <span className="text-red-700 font-mono">{task.FAIL_TO_PASS}</span>
              </div>
            )}
          </div>
        </div>

        {/* Q2: Conventions */}
        <div className="flex flex-col bg-white rounded-lg shadow-sm border border-gray-200 min-h-0">
          <div className="px-4 py-2 border-b border-gray-100 flex items-center space-x-2 bg-gray-50 rounded-t-lg">
            <Shield size={14} className="text-gray-500" />
            <h3 className="text-xs font-bold text-gray-600 uppercase tracking-wide">Active Conventions</h3>
          </div>
          <div className="p-4 overflow-y-auto font-mono text-xs text-gray-700 whitespace-pre-wrap">
            {run?.conventions_content || 'Loading conventions…'}
          </div>
        </div>

        {/* Q3: Aider Live Output */}
        <div className="flex flex-col bg-gray-900 rounded-lg shadow-sm border border-gray-800 min-h-0">
          <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between bg-black rounded-t-lg">
            <div className="flex items-center space-x-2">
              <Terminal size={14} className="text-green-500" />
              <h3 className="text-xs font-bold text-green-500 uppercase tracking-widest">Live Agent Logs</h3>
            </div>
            <div className="flex items-center space-x-3 text-[10px]">
              {tokens && (
                <span className="text-blue-400 font-mono">{formatTokens(tokens)}</span>
              )}
              <span className="text-gray-500 font-mono">{logs.length} lines</span>
            </div>
          </div>
          <div className="p-3 overflow-y-auto font-mono text-xs leading-relaxed whitespace-pre-wrap min-h-0 flex-1">
            {logs.map((line, i) => (
              <div key={i} className="text-gray-300 hover:bg-gray-800 hover:text-green-300 transition-colors">
                {line}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>

        {/* Q4: Patch View */}
        <div className="flex flex-col bg-white rounded-lg shadow-sm border border-gray-200 min-h-0">
          <div className="px-4 py-2 border-b border-gray-100 flex items-center justify-between bg-gray-50 rounded-t-lg">
            <div className="flex items-center space-x-2">
              <Code size={14} className="text-gray-500" />
              <h3 className="text-xs font-bold text-gray-600 uppercase tracking-wide">Patch in Progress</h3>
            </div>
            <div className="flex space-x-2 text-[10px] font-bold">
              <span className="text-blue-600">{patchStats.files} files</span>
              <span className="text-green-600">+{patchStats.added}</span>
              <span className="text-red-600">-{patchStats.removed}</span>
            </div>
          </div>
          <div className="p-3 overflow-y-auto font-mono text-xs text-gray-600 whitespace-pre min-h-0 flex-1">
            {patch ? (
              <pre className="whitespace-pre-wrap">{patch}</pre>
            ) : (
              <span className="text-gray-400 italic">Waiting for agent to produce changes…</span>
            )}
          </div>
        </div>
      </div>

      {/* ── Event Timeline ── */}
      {events.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-3">
          <h4 className="text-[10px] font-bold text-gray-400 uppercase mb-2 tracking-widest">Event Timeline</h4>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-mono">
            {events.map((ev, i) => (
              <span key={i} className="text-gray-500">
                <span className="text-gray-300">[{ev.ts}]</span>{' '}
                <span className={
                  ev.type === 'phase' ? 'text-blue-600' :
                  ev.type === 'patch' ? 'text-green-600' :
                  ev.type === 'done' ? 'text-green-400' :
                  ev.type === 'abort' ? 'text-red-600' :
                  ev.type === 'error' ? 'text-red-400' :
                  'text-gray-500'
                }>[{ev.type}]</span>{' '}
                <span className="text-gray-700">{ev.msg}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MonitorPage;
