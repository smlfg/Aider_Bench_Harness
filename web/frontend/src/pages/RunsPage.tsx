import React, { useEffect, useState } from 'react';
import { fetchRuns } from '../lib/api';
import type { Run } from '../lib/api';
import { Link } from 'react-router-dom';
import { CheckCircle2, XCircle, AlertCircle, ExternalLink } from 'lucide-react';

const RunsPage: React.FC = () => {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    fetchRuns().then(data => {
      setRuns(data);
      setLoading(false);
    });
  }, []);

  const filtered = runs.filter(r => 
    r.run_id.toLowerCase().includes(filter.toLowerCase()) ||
    r.task_id.toLowerCase().includes(filter.toLowerCase()) ||
    r.condition_id.toLowerCase().includes(filter.toLowerCase())
  ).reverse();

  if (loading) return <p>Loading...</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Run Explorer</h2>
        <input
          type="text"
          placeholder="Filter by Run ID, Task, or Condition..."
          className="w-80 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      <div className="bg-white shadow-sm border border-gray-200 rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Run ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Task</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Condition</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Success</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filtered.map((run) => (
              <tr key={run.run_id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  {run.infrastructure_error ? (
                    <AlertCircle className="text-red-500" size={20} />
                  ) : run.task_success ? (
                    <CheckCircle2 className="text-green-500" size={20} />
                  ) : (
                    <XCircle className="text-gray-400" size={20} />
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {run.run_id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {run.task_id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    run.condition_id === 'baseline' ? 'bg-gray-100 text-gray-800' : 'bg-blue-100 text-blue-800'
                  }`}>
                    {run.condition_id}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {run.tests_passed}/{run.tests_total} tests
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-blue-600">
                  <Link to={`/debrief/${run.run_id}`} className="flex items-center space-x-1 hover:underline">
                    <span>View Debrief</span>
                    <ExternalLink size={14} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RunsPage;
