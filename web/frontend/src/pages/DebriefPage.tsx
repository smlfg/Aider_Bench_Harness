import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchRunDetail, judgeRun } from '../lib/api';
import type { Run } from '../lib/api';
import {
  CheckCircle2, XCircle, AlertCircle, Clock, Database,
  ChevronLeft, RotateCcw, Shield, Loader2, Star, ThumbsUp,
  ThumbsDown, Minus, BarChart3
} from 'lucide-react';

const DebriefPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [patch, setPatch] = useState('');
  const [judging, setJudging] = useState(false);
  const [judgeError, setJudgeError] = useState<string | null>(null);

  const reload = () => {
    if (!runId) return;
    setLoading(true);
    fetchRunDetail(runId).then(data => {
      setRun(data);
      setLoading(false);
      if (data.artifacts_dir) {
        fetch(`/api/artifacts/${runId}/git_diff.patch`)
          .then(r => r.text())
          .then(setPatch)
          .catch(() => {});
      }
    });
  };

  useEffect(() => { reload(); }, [runId]);

  const handleJudge = async () => {
    if (!runId) return;
    setJudging(true);
    setJudgeError(null);
    try {
      await judgeRun(runId);
      reload();
    } catch (err: any) {
      setJudgeError(err.message);
      setJudging(false);
    }
  };

  if (loading) return <p>Loading...</p>;
  if (!run) return <p>Run not found</p>;

  const getVerdict = () => {
    if (run.infrastructure_error) return { label: 'Infrastructure Error', color: 'bg-red-500', icon: AlertCircle, text: 'This run was invalid due to a system or provider error. It is excluded from statistics.' };
    if (run.task_success) return { label: 'Task Success', color: 'bg-green-600', icon: CheckCircle2, text: 'The agent successfully resolved the task and passed all FAIL_TO_PASS tests.' };
    return { label: 'Task Failed', color: 'bg-yellow-500', icon: XCircle, text: 'The agent produced a patch, but some tests remain red.' };
  };

  const verdict = getVerdict();
  const Icon = verdict.icon;

  const judgeResult = (run as any).judge_result;
  const verdictIcon = judgeResult?.verdict === 'support' ? ThumbsUp
    : judgeResult?.verdict === 'reject' ? ThumbsDown
    : Minus;

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      {/* Header */}
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

      {/* Verdict Banner */}
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

      {/* Judge Score Card */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="p-3 bg-orange-50 text-orange-600 rounded-lg">
              <BarChart3 size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium">Judge Score</p>
              <p className="text-2xl font-bold text-gray-900">
                {run.judge_score !== null ? run.judge_score.toFixed(1) : '—'}
              </p>
            </div>
          </div>
          {!run.infrastructure_error && run.task_success !== null && (
            <div>
              {run.judge_score === null ? (
                <button
                  onClick={handleJudge}
                  disabled={judging}
                  className="flex items-center space-x-2 px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-sm disabled:bg-indigo-300 transition-colors"
                >
                  {judging ? <Loader2 size={16} className="animate-spin" /> : <Shield size={16} />}
                  <span>{judging ? 'Judging...' : 'Run Judge'}</span>
                </button>
              ) : (
                <span className="text-xs text-gray-400 italic">judged</span>
              )}
            </div>
          )}
        </div>
        {judgeError && (
          <div className="mt-3 text-sm text-red-600 bg-red-50 p-3 rounded">{judgeError}</div>
        )}
      </div>

      {/* Judge Result Details */}
      {judgeResult && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
            <h3 className="font-bold text-gray-700 uppercase tracking-wider text-sm flex items-center space-x-2">
              <Star size={16} />
              <span>Judge Assessment</span>
            </h3>
            <div className="flex items-center space-x-2">
              {React.createElement(verdictIcon, { size: 16, className: judgeResult.verdict === 'support' ? 'text-green-600' : judgeResult.verdict === 'reject' ? 'text-red-600' : 'text-gray-400' })}
              <span className={`text-sm font-bold uppercase ${
                judgeResult.verdict === 'support' ? 'text-green-700' :
                judgeResult.verdict === 'reject' ? 'text-red-700' : 'text-gray-600'
              }`}>{judgeResult.verdict}</span>
            </div>
          </div>
          <div className="p-6 space-y-6">
            {/* Rubric Scores */}
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: 'Scope Adherence', key: 'scope_adherence' },
                { label: 'Minimality', key: 'minimality' },
                { label: 'Diff Clarity', key: 'diff_clarity' },
              ].map(({ label, key }) => (
                <div key={key} className="bg-gray-50 p-4 rounded-lg text-center">
                  <div className="text-3xl font-bold text-indigo-700">{judgeResult[key]}</div>
                  <div className="text-xs text-gray-500 mt-1">{label}</div>
                </div>
              ))}
            </div>
            {/* Rationale */}
            <div>
              <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Rationale</h4>
              <p className="text-sm text-gray-700 leading-relaxed">{judgeResult.rationale}</p>
            </div>
            {/* Conclusion */}
            <div>
              <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Conclusion</h4>
              <p className="text-sm text-gray-700 leading-relaxed">{judgeResult.conclusion}</p>
            </div>
          </div>
        </div>
      )}

      {/* Stats Grid */}
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
          <div className="p-3 bg-gray-100 text-gray-600 rounded-lg">
            <Shield size={24} />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Condition</p>
            <p className="text-lg font-bold font-mono text-gray-900">{run.condition_id}</p>
          </div>
        </div>
      </div>

      {/* Patch Diff */}
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

      {/* Error Details */}
      {run.infrastructure_error && (
        <div className="bg-white rounded-lg shadow-sm border border-red-200 p-6">
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
