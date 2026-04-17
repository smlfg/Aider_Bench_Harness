import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchRunDetail } from '../lib/api';
import type { Run } from '../lib/api';
import { CheckCircle2, XCircle, AlertCircle, Clock, Database, ChevronLeft, RotateCcw } from 'lucide-react';

const DebriefPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [patch, setPatch] = useState('');

  useEffect(() => {
    if (!runId) return;
    fetchRunDetail(runId).then(data => {
      setRun(data);
      setLoading(false);
      // Fetch patch if available
      if (data.artifacts_dir) {
        fetch(`/api/artifacts/${runId}/git_diff.patch`)
          .then(r => r.text())
          .then(setPatch)
          .catch(() => {});
      }
    });
  }, [runId]);

  if (loading) return <p>Loading...</p>;
  if (!run) return <p>Run not found</p>;

  const getVerdict = () => {
    if (run.infrastructure_error) return { label: 'Infrastructure Error', color: 'bg-red-500', icon: AlertCircle, text: 'This run was invalid due to a system or provider error. It is excluded from statistics.' };
    if (run.task_success) return { label: 'Task Success', color: 'bg-green-600', icon: CheckCircle2, text: 'The agent successfully resolved the task and passed all FAIL_TO_PASS tests.' };
    return { label: 'Task Failed', color: 'bg-yellow-500', icon: XCircle, text: 'The agent produced a patch, but some tests remain red.' };
  };

  const verdict = getVerdict();
  const Icon = verdict.icon;

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <div className="flex items-center justify-between">
        <Link to="/runs" className="flex items-center text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <ChevronLeft size={16} />
          <span>Back to Runs</span>
        </Link>
        <Link to="/launch" className="flex items-center space-x-2 px-4 py-2 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors">
          <RotateCcw size={16} />
          <span>New Run</span>
        </Link>
      </div>

      <div className={`${verdict.color} rounded-lg shadow-lg p-6 text-white`}>
        <div className="flex items-center space-x-4">
          <div className="p-3 bg-white/20 rounded-full">
            <Icon size={32} />
          </div>
          <div>
            <h2 className="text-3xl font-bold">{verdict.label}</h2>
            <p className="text-white/80 mt-1">{verdict.text}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 flex items-center space-x-4">
          <div className="p-3 bg-blue-50 text-blue-600 rounded-lg">
            <Clock size={24} />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Duration</p>
            <p className="text-xl font-bold text-gray-900">{run.duration_seconds?.toFixed(1)}s</p>
          </div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 flex items-center space-x-4">
          <div className="p-3 bg-purple-50 text-purple-600 rounded-lg">
            <Database size={24} />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Test Results</p>
            <p className="text-xl font-bold text-gray-900">{run.tests_passed} / {run.tests_total}</p>
          </div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 flex items-center space-x-4">
          <div className="p-3 bg-orange-50 text-orange-600 rounded-lg">
            <AlertCircle size={24} />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Judge Score</p>
            <p className="text-xl font-bold text-gray-900">{run.judge_score || 'N/A'}</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
          <h3 className="font-bold text-gray-700 uppercase tracking-wider text-sm">Final Patch Diff</h3>
          <span className="text-xs font-mono text-gray-500">{run.files_changed} files changed</span>
        </div>
        <div className="p-6">
          {patch ? (
            <pre className="bg-gray-900 text-gray-300 p-4 rounded text-xs overflow-x-auto font-mono">
              {patch}
            </pre>
          ) : (
            <p className="text-gray-400 italic text-center py-8">No patch was produced by the agent.</p>
          )}
        </div>
      </div>

      {run.infrastructure_error && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-bold text-red-700 uppercase tracking-wider text-sm mb-4">Error Details</h3>
          <pre className="bg-red-50 text-red-900 p-4 rounded text-xs overflow-x-auto font-mono">
            {run.error_detail}
          </pre>
        </div>
      )}
    </div>
  );
};

export default DebriefPage;
