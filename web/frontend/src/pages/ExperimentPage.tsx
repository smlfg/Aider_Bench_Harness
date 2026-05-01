import React, { useEffect, useState, useCallback } from 'react';
import {
  fetchTasks,
  fetchConventions,
  createExperiment,
  startExperiment,
  fetchExperimentStatus,
  type Task,
  type Convention,
  type ExperimentPlan,
  type ExperimentStatus,
} from '../lib/api';
import { Play, Loader2, FlaskConical, Layers, ArrowRight, CheckCircle2, XCircle, Clock, BarChart3 } from 'lucide-react';

const ExperimentPage: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [conventions, setConventions] = useState<Convention[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([]);
  const [baseMd, setBaseMd] = useState('CONVENTIONS.baseline.md');
  const [targetMd, setTargetMd] = useState('KarparthysClaude.md');
  const [parts, setParts] = useState(4);
  const [repsPerPart, setRepsPerPart] = useState(5);
  const [parallel, setParallel] = useState(10);

  const [plan, setPlan] = useState<ExperimentPlan | null>(null);
  const [status, setStatus] = useState<ExperimentStatus | null>(null);
  const [phase, setPhase] = useState<'config' | 'ready' | 'running' | 'done'>('config');
  const [launching, setLaunching] = useState(false);

  useEffect(() => {
    Promise.all([fetchTasks(), fetchConventions()]).then(([t, c]) => {
      setTasks(t);
      setConventions(c);
      setLoading(false);
    });
  }, []);

  const handleConfigure = async () => {
    setError(null);
    try {
      const p = await createExperiment({
        task_ids: selectedTaskIds,
        base_md: baseMd,
        target_md: targetMd,
        parts,
        reps_per_part: repsPerPart,
        parallel,
      });
      setPlan(p);
      setPhase('ready');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleStart = async () => {
    if (!plan) return;
    setLaunching(true);
    setError(null);
    try {
      await startExperiment(plan.exp_id);
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
        const s = await fetchExperimentStatus(expId);
        setStatus(s);
        if (s.status === 'completed' || (s.running === 0 && s.completed + s.failed >= s.total_runs)) {
          setPhase('done');
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 3000);
  }, []);

  const toggleTask = (id: string) => {
    setSelectedTaskIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  if (loading) return <p className="text-gray-400 animate-pulse">Loading...</p>;

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <h2 className="text-2xl font-bold text-gray-900 flex items-center space-x-2">
        <FlaskConical size={24} className="text-indigo-600" />
        <span>Iterative Experiment</span>
      </h2>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded text-red-700 text-sm">{error}</div>
      )}

      {/* ── Config Phase ── */}
      {phase === 'config' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Task Selection */}
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
              <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4 flex items-center space-x-2">
                <Layers size={16} />
                <span>Tasks (Tier A)</span>
              </h3>
              <div className="space-y-2">
                {tasks
                  .filter(t => t.instance_id?.startsWith('astropy__astropy-14') || t.instance_id?.startsWith('astropy__astropy-13'))
                  .slice(0, 10)
                  .map(t => {
                    const id = t.instance_id || t.task_id || '';
                    const selected = selectedTaskIds.includes(id);
                    return (
                      <label key={id} className={`flex items-center space-x-3 p-3 rounded-lg cursor-pointer transition-colors ${selected ? 'bg-indigo-50 border border-indigo-200' : 'bg-gray-50 border border-gray-200 hover:bg-gray-100'}`}>
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleTask(id)}
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="font-mono text-sm text-gray-900">{id}</span>
                        <span className="text-xs text-gray-400">{t.repo}</span>
                      </label>
                    );
                  })}
              </div>
            </div>

            {/* MD Selection */}
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 space-y-4">
              <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-2">Conventions</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Base (.md)</label>
                  <select
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                    value={baseMd}
                    onChange={e => setBaseMd(e.target.value)}
                  >
                    {conventions.filter(c => c.name.includes('baseline') || c.name === 'CONVENTIONS.baseline.md').map(c => (
                      <option key={c.path} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Target (.md)</label>
                  <select
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                    value={targetMd}
                    onChange={e => setTargetMd(e.target.value)}
                  >
                    {conventions.map(c => (
                      <option key={c.path} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Parameters */}
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 space-y-5">
              <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider">Parameters</h3>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Parts <span className="text-gray-400 font-normal">(Quartile: {parts})</span>
                </label>
                <input
                  type="range"
                  min={2}
                  max={40}
                  value={parts}
                  onChange={e => setParts(Number(e.target.value))}
                  className="w-full accent-indigo-600"
                />
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>2</span><span>10</span><span>20</span><span>40</span>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Reps per Part <span className="text-gray-400 font-normal">({repsPerPart})</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={repsPerPart}
                  onChange={e => setRepsPerPart(Number(e.target.value))}
                  className="w-full accent-indigo-600"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Max Parallel <span className="text-gray-400 font-normal">({Math.min(parallel, 10)})</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={Math.min(parallel, 10)}
                  onChange={e => setParallel(Number(e.target.value))}
                  className="w-full accent-indigo-600"
                />
              </div>

              <div className="pt-4 border-t border-gray-100">
                <div className="text-center space-y-1">
                  <div className="text-3xl font-bold text-indigo-600">
                    {(parts + 1) * selectedTaskIds.length * repsPerPart || '—'}
                  </div>
                  <div className="text-xs text-gray-500">Total Runs</div>
                  <div className="text-xs text-gray-400">
                    {parts + 1} conditions × {selectedTaskIds.length} tasks × {repsPerPart} reps
                  </div>
                </div>
              </div>

              <button
                onClick={handleConfigure}
                disabled={selectedTaskIds.length === 0}
                className="w-full flex items-center justify-center space-x-2 py-3 px-4 border border-transparent rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-gray-400 transition-colors"
              >
                <ArrowRight size={18} />
                <span>Configure Experiment</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Ready Phase (Plan Review) ── */}
      {phase === 'ready' && plan && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">Experiment Plan</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-gray-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">{plan.conditions.length}</div>
                <div className="text-xs text-gray-500">Conditions</div>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">{plan.task_ids.length}</div>
                <div className="text-xs text-gray-500">Tasks</div>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">{plan.reps_per_part}</div>
                <div className="text-xs text-gray-500">Reps</div>
              </div>
              <div className="bg-indigo-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-indigo-600">{plan.total_runs}</div>
                <div className="text-xs text-indigo-500">Total Runs</div>
              </div>
            </div>

            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-gray-500 border-b border-gray-200">
                  <th className="pb-2">Condition</th>
                  <th className="pb-2">§ Sections</th>
                  <th className="pb-2">.md File</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {plan.conditions.map(c => (
                  <tr key={c.condition_id}>
                    <td className="py-2 font-mono">{c.condition_id}</td>
                    <td className="py-2">{c.sections === 0 ? 'baseline only' : `§1–§${c.sections}`}</td>
                    <td className="py-2 text-gray-500 text-xs">{c.md_path.split('/').pop()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex space-x-4">
            <button
              onClick={() => { setPhase('config'); setPlan(null); }}
              className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Back
            </button>
            <button
              onClick={handleStart}
              disabled={launching}
              className="flex items-center space-x-2 px-8 py-3 border border-transparent rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:bg-gray-400 transition-colors"
            >
              {launching ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
              <span>{launching ? 'Launching...' : `Launch ${plan.total_runs} Runs`}</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Running / Done Phase ── */}
      {(phase === 'running' || phase === 'done') && status && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-white p-4 rounded-lg border border-gray-200 text-center">
              <div className="text-2xl font-bold text-gray-900">{status.total_runs}</div>
              <div className="text-xs text-gray-500">Total</div>
            </div>
            <div className="bg-green-50 p-4 rounded-lg border border-green-200 text-center">
              <div className="text-2xl font-bold text-green-700 flex items-center justify-center space-x-1">
                <CheckCircle2 size={20} />
                <span>{status.success}</span>
              </div>
              <div className="text-xs text-green-600">Success</div>
            </div>
            <div className="bg-red-50 p-4 rounded-lg border border-red-200 text-center">
              <div className="text-2xl font-bold text-red-700 flex items-center justify-center space-x-1">
                <XCircle size={20} />
                <span>{status.failed}</span>
              </div>
              <div className="text-xs text-red-600">Failed</div>
            </div>
            <div className="bg-blue-50 p-4 rounded-lg border border-blue-200 text-center">
              <div className="text-2xl font-bold text-blue-700 flex items-center justify-center space-x-1">
                <Clock size={20} />
                <span>{status.running}</span>
              </div>
              <div className="text-xs text-blue-600">Running</div>
            </div>
            <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-200 text-center">
              <div className="text-2xl font-bold text-indigo-700 flex items-center justify-center space-x-1">
                <BarChart3 size={20} />
                <span>{status.completed > 0 ? ((status.success / status.completed) * 100).toFixed(0) + '%' : '—'}</span>
              </div>
              <div className="text-xs text-indigo-600">Success Rate</div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">Progress</span>
              <span className="text-sm text-gray-500">{status.completed}/{status.total_runs} runs</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-green-500 transition-all duration-500" style={{ width: `${status.total_runs > 0 ? (status.completed / status.total_runs * 100) : 0}%` }} />
            </div>
          </div>

          {/* Conditions Table */}
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">Condition Results</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-gray-500 border-b border-gray-200">
                  <th className="pb-2">Condition</th>
                  <th className="pb-2">§ Sections</th>
                  <th className="pb-2">Runs</th>
                  <th className="pb-2">Success</th>
                  <th className="pb-2">Rate</th>
                  <th className="pb-2">Judge Score</th>
                  <th className="pb-2">Avg Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {status.conditions.map(c => (
                  <tr key={c.condition_id} className={c.condition_id === 'baseline' ? 'bg-gray-50' : ''}>
                    <td className="py-2 font-mono font-medium">{c.condition_id}</td>
                    <td className="py-2 text-gray-500">{c.sections === 0 ? '—' : `§1–§${c.sections}`}</td>
                    <td className="py-2">{c.completed}/{c.total}</td>
                    <td className="py-2">{c.success}</td>
                    <td className="py-2">
                      {c.completed > 0 ? (
                        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${c.success / c.completed >= 0.5 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          {(c.success / c.completed * 100).toFixed(0)}%
                        </span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="py-2">{c.avg_judge_score !== null ? c.avg_judge_score : '—'}</td>
                    <td className="py-2 text-gray-500">{c.avg_duration !== null ? `${c.avg_duration}s` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {phase === 'running' && (
            <p className="text-sm text-gray-400 text-center animate-pulse">Auto-refreshing every 3 seconds...</p>
          )}

          {phase === 'done' && (
            <div className="text-center">
              <button
                onClick={() => { setPhase('config'); setPlan(null); setStatus(null); }}
                className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                New Experiment
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ExperimentPage;
