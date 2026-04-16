import React, { useEffect, useState } from 'react';
import { fetchTasks, fetchConventions, launchRun, Task, Convention } from '../lib/api';
import { useNavigate } from 'react-router-dom';
import { Play, Loader2 } from 'lucide-react';

const LaunchPage: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [conventions, setConventions] = useState<Convention[]>([]);
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    task_id: '',
    condition: 'candidate_v1',
    iteration: 1,
    run_index: 1,
    conventions_path: '',
  });

  useEffect(() => {
    Promise.all([fetchTasks(), fetchConventions()]).then(([t, c]) => {
      setTasks(t);
      setConventions(c);
      if (t.length > 0) setFormData(prev => ({ ...prev, task_id: t[0].instance_id || t[0].task_id || '' }));
      if (c.length > 0) setFormData(prev => ({ ...prev, conventions_path: c[0].path }));
      setLoading(false);
    });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLaunching(true);
    setError(null);
    try {
      const res = await launchRun(formData);
      navigate(`/monitor/${res.run_id}`);
    } catch (err: any) {
      setError(err.message);
      setLaunching(false);
    }
  };

  const selectedTask = tasks.find(t => (t.instance_id || t.task_id) === formData.task_id);

  if (loading) return <p>Loading...</p>;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <h2 className="text-2xl font-bold text-gray-900">Launch New Experiment Run</h2>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <form onSubmit={handleSubmit} className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700">Select Task</label>
            <select
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              value={formData.task_id}
              onChange={(e) => setFormData({ ...formData, task_id: e.target.value })}
            >
              {tasks.map(t => (
                <option key={t.instance_id || t.task_id} value={t.instance_id || t.task_id}>
                  {t.instance_id || t.task_id} ({t.repo})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Condition ID</label>
            <input
              type="text"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              value={formData.condition}
              onChange={(e) => setFormData({ ...formData, condition: e.target.value })}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Conventions File</label>
            <select
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              value={formData.conventions_path}
              onChange={(e) => setFormData({ ...formData, conventions_path: e.target.value })}
            >
              {conventions.map(c => (
                <option key={c.path} value={c.path}>{c.name}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Iteration</label>
              <input
                type="number"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                value={formData.iteration}
                onChange={(e) => setFormData({ ...formData, iteration: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Run Index</label>
              <input
                type="number"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                value={formData.run_index}
                onChange={(e) => setFormData({ ...formData, run_index: Number(e.target.value) })}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={launching}
            className="w-full flex items-center justify-center space-x-2 py-3 px-4 border border-transparent rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400"
          >
            {launching ? <Loader2 className="animate-spin" size={20} /> : <Play size={20} />}
            <span>{launching ? 'Launching...' : 'Start Run'}</span>
          </button>
        </form>

        <div className="space-y-6">
          <div className="bg-gray-50 p-6 rounded-lg border border-gray-200">
            <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">Task Preview</h3>
            {selectedTask ? (
              <div className="space-y-4">
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">{selectedTask.instance_id || selectedTask.task_id}</h4>
                  <p className="text-sm text-gray-600">{selectedTask.repo}</p>
                </div>
                <div className="bg-white p-3 rounded border border-gray-200 text-xs font-mono max-h-60 overflow-y-auto whitespace-pre-wrap">
                  {selectedTask.problem_statement}
                </div>
              </div>
            ) : (
              <p className="text-gray-400 italic">No task selected</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default LaunchPage;
