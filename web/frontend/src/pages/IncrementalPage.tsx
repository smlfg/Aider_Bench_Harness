import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchTasks, fetchConventions,
  createIncremental, launchIncremental, fetchIncrementalStatus,
  type Task, type Convention, type IncrementalPlan, type IncrementalStatus,
} from '../lib/api';
import {
  FlaskConical, Play, Loader2, ChevronLeft, ArrowRight,
  CheckCircle2, XCircle, Clock, BarChart3,
} from 'lucide-react';

const TIER_A = ['astropy__astropy-14182', 'astropy__astropy-14365', 'astropy__astropy-13398'];

const IncrementalPage: React.FC = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [conventions, setConventions] = useState<Convention[]>([]);
  const [loading, setLoading] = useState(true);

  const [taskId, setTaskId] = useState('astropy__astropy-14182');
  const [baseMd, setBaseMd] = useState('CONVENTIONS.baseline.md');
  const [incrementMd, setIncrementMd] = useState('KarparthysClaude.md');
  const [repetitions, setRepetitions] = useState(3);
  const [parallel, setParallel] = useState(10);

  const [plan, setPlan] = useState<IncrementalPlan | null>(null);
  const [status, setStatus] = useState<IncrementalStatus | null>(null);
  const [phase, setPhase] = useState<'config' | 'ready' | 'running' | 'done'>('config');
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchTasks(), fetchConventions()]).then(([t, c]) => {
      setTasks(t);
      setConventions(c);
      setLoading(false);
    });
  }, []);

  const tierATasks = tasks.filter(t => {
    const id = t.instance_id || t.task_id || '';
    return TIER_A.includes(id) || id.startsWith('astropy__astropy-1');
  });

  const handleConfigure = async () => {
    setError(null);
    try {
      const p = await createIncremental({
        task_id: taskId,
        base_md: baseMd,
        increment_md: incrementMd,
        repetitions,
        iteration: 1,
        parallel,
      });
      setPlan(p);
      setPhase('ready');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleLaunch = async () => {
    if (!plan) return;
    setLaunching(true);
    setError(null);
    try {
      await launchIncremental(plan.exp_id);
      setPhase('running');
      pollStatus(plan.exp_id);
    } catch (err: any) {
      setError(err.message);
      setLaunching(false);
    }
  };

  const pollStatus = useCallback((expId: string) => {
    const interval = setInterval(async () => {
      try {
        const s = await fetchIncrementalStatus(expId);
        setStatus(s);
        if (s.status === 'completed') {
          setPhase('done');
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 3000);
  }, []);

  const totalRuns = plan ? plan.total_runs : 0;
  const doneRuns = status ? status.completed + status.failed : 0;
  const progress = totalRuns > 0 ? (doneRuns / totalRuns) * 100 : 0;

  if (loading) return <p className="text-gray-400 animate-pulse p-6">Loading...</p>;

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-12">
      <div className="flex items-center space-x-4">
        <button onClick={() => navigate('/')} className="flex items-center text-sm text-gray-500 hover:text-gray-900">
          <ChevronLeft size={16} />
          <span>Back</span>
        </button>
        <h2 className="text-2xl font-bold text-gray-900 flex items-center space-x-2">
          <FlaskConical size={22} className="text-indigo-600" />
          <span>Kernmessung</span>
        </h2>
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded text-red-700 text-sm">{error}</div>
      )}

      {/* ── Config ── */}
      {phase === 'config' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Task */}
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Task (Tier A)</h3>
              <div className="space-y-1">
                {tierATasks.slice(0, 8).map(t => {
                  const id = t.instance_id || t.task_id || '';
                  return (
                    <label key={id} className={`flex items-center space-x-3 p-3 rounded-lg cursor-pointer transition-colors ${taskId === id ? 'bg-indigo-50 border border-indigo-300' : 'bg-gray-50 border border-gray-200 hover:bg-gray-100'}`}>
                      <input type="radio" name="task" value={id} checked={taskId === id} onChange={() => setTaskId(id)} className="text-indigo-600" />
                      <span className="font-mono text-sm text-gray-900">{id}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            {/* MDs */}
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Conventions</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Base (.md)</label>
                  <select className="w-full rounded border-gray-300 shadow-sm text-sm" value={baseMd} onChange={e => setBaseMd(e.target.value)}>
                    {conventions.filter(c => c.name.includes('baseline') || c.name === 'CONVENTIONS.baseline.md').map(c => (
                      <option key={c.name} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Increment (.md)</label>
                  <select className="w-full rounded border-gray-300 shadow-sm text-sm" value={incrementMd} onChange={e => setIncrementMd(e.target.value)}>
                    {conventions.filter(c => c.name.includes('KarparthysClaude') || c.name.includes('R01') || c.name.includes('S01')).map(c => (
                      <option key={c.name} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Params */}
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 space-y-5">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Parameters</h3>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Repetitions <span className="text-gray-400 font-normal">({repetitions})</span></label>
                <input type="range" min={1} max={10} value={repetitions} onChange={e => setRepetitions(Number(e.target.value))} className="w-full accent-indigo-600" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Parallel <span className="text-gray-400 font-normal">({Math.min(parallel, 10)})</span></label>
                <input type="range" min={1} max={10} value={Math.min(parallel, 10)} onChange={e => setParallel(Number(e.target.value))} className="w-full accent-indigo-600" />
              </div>
              <div className="pt-4 border-t border-gray-100">
                <div className="text-center space-y-1">
                  <div className="text-3xl font-bold text-indigo-600">
                    {plan ? plan.total_runs : '—'}
                  </div>
                  <div className="text-xs text-gray-500">Total Runs</div>
                </div>
              </div>
              <button
                onClick={handleConfigure}
                disabled={!taskId}
                className="w-full flex items-center justify-center space-x-2 py-3 px-4 border border-transparent rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 transition-colors"
              >
                <ArrowRight size={18} />
                <span>Configure Experiment</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Ready ── */}
      {phase === 'ready' && plan && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">Experiment Plan</h3>
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-gray-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">{plan.total_lines}</div>
                <div className="text-xs text-gray-500">Increment Lines</div>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">{plan.variants.length}</div>
                <div className="text-xs text-gray-500">Variants (k=0..N)</div>
              </div>
              <div className="bg-indigo-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-indigo-600">{plan.total_runs}</div>
                <div className="text-xs text-indigo-500">Total Runs</div>
              </div>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-gray-500 border-b border-gray-200">
                  <th className="pb-2">k</th>
                  <th className="pb-2">Condition</th>
                  <th className="pb-2">Lines added</th>
                  <th className="pb-2">Runs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {plan.variants.map(v => (
                  <tr key={v.condition_id} className={v.k === 0 ? 'bg-gray-50 font-medium' : ''}>
                    <td className="py-2 font-mono">{v.k}</td>
                    <td className="py-2 font-mono text-xs">{v.condition_id}</td>
                    <td className="py-2 text-gray-500">{v.k === 0 ? 'baseline only' : `${v.k} lines`}</td>
                    <td className="py-2">{repetitions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex space-x-4">
            <button onClick={() => { setPhase('config'); setPlan(null); }} className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50">Back</button>
            <button onClick={handleLaunch} disabled={launching} className="flex items-center space-x-2 px-8 py-3 border border-transparent rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 disabled:bg-gray-400 transition-colors">
              {launching ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
              <span>{launching ? 'Launching...' : `Launch ${plan.total_runs} Runs`}</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Running / Done ── */}
      {(phase === 'running' || phase === 'done') && status && (
        <div className="space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-white p-4 rounded-lg border border-gray-200 text-center">
              <div className="text-2xl font-bold text-gray-900">{status.total_runs}</div>
              <div className="text-xs text-gray-500">Total</div>
            </div>
            <div className="bg-green-50 p-4 rounded-lg border border-green-200 text-center">
              <div className="text-2xl font-bold text-green-700 flex items-center justify-center space-x-1">
                <CheckCircle2 size={20} /><span>{status.success}</span>
              </div>
              <div className="text-xs text-green-600">Success</div>
            </div>
            <div className="bg-red-50 p-4 rounded-lg border border-red-200 text-center">
              <div className="text-2xl font-bold text-red-700 flex items-center justify-center space-x-1">
                <XCircle size={20} /><span>{status.failed}</span>
              </div>
              <div className="text-xs text-red-600">Failed</div>
            </div>
            <div className="bg-blue-50 p-4 rounded-lg border border-blue-200 text-center">
              <div className="text-2xl font-bold text-blue-700 flex items-center justify-center space-x-1">
                <Clock size={20} /><span>{status.running}</span>
              </div>
              <div className="text-xs text-blue-600">Running</div>
            </div>
            <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-200 text-center">
              <div className="text-2xl font-bold text-indigo-700 flex items-center justify-center space-x-1">
                <BarChart3 size={20} /><span>{status.pending}</span>
              </div>
              <div className="text-xs text-indigo-600">Pending</div>
            </div>
          </div>

          {/* Progress */}
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">Progress</span>
              <span className="text-sm text-gray-500">{doneRuns}/{status.total_runs} runs</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-green-500 transition-all duration-500" style={{ width: `${progress}%` }} />
            </div>
          </div>

          {/* Results per k */}
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">Results by k (incremental lines added)</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wider text-gray-500 border-b border-gray-200">
                    <th className="pb-2">k</th>
                    <th className="pb-2">Runs</th>
                    <th className="pb-2">Success</th>
                    <th className="pb-2">Judge Score μ</th>
                    <th className="pb-2">σ</th>
                    <th className="pb-2">Avg Duration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {status.variants_k.map(r => (
                    <tr key={r.k} className={r.k === 0 ? 'bg-gray-50 font-medium' : ''}>
                      <td className="py-2 font-mono">{r.k}</td>
                      <td className="py-2">{r.runs_completed}/{repetitions}</td>
                      <td className="py-2">
                        {r.runs_success > 0 ? (
                          <span className="inline-flex items-center space-x-1 text-green-700">
                            <CheckCircle2 size={14} /><span>{r.runs_success}</span>
                          </span>
                        ) : r.runs_completed === 0 ? (
                          <span className="text-gray-300">—</span>
                        ) : (
                          <span className="text-red-700">{r.runs_success}</span>
                        )}
                      </td>
                      <td className="py-2">
                        {r.judge_score_mean !== null ? (
                          <span className="font-bold text-indigo-700">{r.judge_score_mean.toFixed(2)}</span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="py-2">
                        {r.judge_score_std !== null ? (
                          <span className="text-gray-500">±{r.judge_score_std.toFixed(2)}</span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="py-2 text-gray-500">
                        {r.duration_mean !== null ? `${r.duration_mean.toFixed(0)}s` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-gray-400 mt-3 italic">
              Judge scores are populated manually via the "Run Judge" button on each run's Debrief page.
              After judging, refresh this page to see updated averages.
            </p>
          </div>

          {phase === 'running' && (
            <p className="text-sm text-gray-400 text-center animate-pulse">Auto-refreshing every 3 seconds...</p>
          )}

          {phase === 'done' && (
            <div className="text-center">
              <button onClick={() => { setPhase('config'); setPlan(null); setStatus(null); }} className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50">
                New Experiment
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default IncrementalPage;
