import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchRunDetail, abortRun } from '../lib/api';
import type { Run } from '../lib/api';
import type { Task } from '../lib/api';
import { Shield, FileText, Terminal, Code, StopCircle } from 'lucide-react';

const MonitorPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<Run | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [phase, setPhase] = useState('initializing');
  const [logs, setLogs] = useState<string[]>([]);
  const [patch, setPatch] = useState('');
  const [patchStats, setPatchStats] = useState({ files: 0, added: 0, removed: 0 });
  const [isDone, setIsDone] = useState(false);

  const logEndRef = useRef<HTMLDivElement>(null);

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
    });

    eventSource.addEventListener('log', (e) => {
      const data = JSON.parse(e.data);
      setLogs(prev => [...prev, data.content]);
    });

    eventSource.addEventListener('patch_changed', (e) => {
      const data = JSON.parse(e.data);
      setPatch(data.patch);
      setPatchStats({ files: data.files_changed, added: data.lines_added, removed: data.lines_removed });
    });

    eventSource.addEventListener('done', () => {
      setIsDone(true);
      eventSource.close();
      // Wait a bit to show the "done" state before redirecting
      setTimeout(() => navigate(`/debrief/${runId}`), 2000);
    });

    return () => eventSource.close();
  }, [runId, navigate]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleAbort = async () => {
    if (runId) await abortRun(runId);
  };

  if (!runId) return <div>Missing Run ID</div>;

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col space-y-4">
      <div className="flex items-center justify-between bg-white p-4 rounded-lg shadow-sm border border-gray-200">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-bold text-gray-500 uppercase">Phase:</span>
            <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-bold animate-pulse uppercase">
              {phase.replace('_', ' ')}
            </span>
          </div>
          <div className="h-4 w-px bg-gray-300" />
          <div className="text-sm">
            <span className="text-gray-500">Run ID:</span> <span className="font-mono font-bold">{runId}</span>
          </div>
        </div>
        {!isDone && (
          <button 
            onClick={handleAbort}
            className="flex items-center space-x-2 px-4 py-2 bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 transition-colors"
          >
            <StopCircle size={18} />
            <span>Abort Run</span>
          </button>
        )}
      </div>

      <div className="flex-1 grid grid-cols-2 gap-4 min-h-0">
        {/* Left Column */}
        <div className="flex flex-col space-y-4 min-h-0">
          {/* Q1: Task */}
          <div className="flex-1 bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col min-h-0">
            <div className="px-4 py-2 border-b border-gray-100 flex items-center space-x-2 bg-gray-50 rounded-t-lg">
              <FileText size={16} className="text-gray-500" />
              <h3 className="text-sm font-bold text-gray-700 uppercase">Task Definition</h3>
            </div>
            <div className="p-4 overflow-y-auto text-sm">
              <h4 className="font-bold text-gray-900">{run?.task_id}</h4>
<p className="mt-2 text-gray-600 whitespace-pre-wrap font-sans leading-relaxed">
                  {task?.problem_statement || 'Fetching task details...'}
                </p>
            </div>
          </div>
          {/* Q2: Conventions */}
          <div className="h-1/3 bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col min-h-0">
            <div className="px-4 py-2 border-b border-gray-100 flex items-center space-x-2 bg-gray-50 rounded-t-lg">
              <Shield size={16} className="text-gray-500" />
              <h3 className="text-sm font-bold text-gray-700 uppercase">Active Conventions</h3>
            </div>
            <div className="p-4 overflow-y-auto text-xs font-mono text-gray-700">
              {run?.conventions_content || 'Loading conventions...'}
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="flex flex-col space-y-4 min-h-0">
          {/* Q3: Aider Output */}
          <div className="flex-1 bg-gray-900 rounded-lg shadow-sm border border-gray-800 flex flex-col min-h-0">
            <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between bg-black rounded-t-lg">
              <div className="flex items-center space-x-2">
                <Terminal size={16} className="text-green-500" />
                <h3 className="text-sm font-bold text-green-500 uppercase tracking-widest">Live Agent Logs</h3>
              </div>
              {logs.length > 0 && <span className="text-[10px] text-gray-500 font-mono">Lines: {logs.length}</span>}
            </div>
            <div className="p-4 overflow-y-auto font-mono text-xs text-gray-300 whitespace-pre-wrap">
              {logs.join('')}
              <div ref={logEndRef} />
            </div>
          </div>
          {/* Q4: Patch View */}
          <div className="h-1/3 bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col min-h-0">
            <div className="px-4 py-2 border-b border-gray-100 flex items-center justify-between bg-gray-50 rounded-t-lg">
              <div className="flex items-center space-x-2">
                <Code size={16} className="text-gray-500" />
                <h3 className="text-sm font-bold text-gray-700 uppercase">Patch in Progress</h3>
              </div>
              <div className="flex space-x-2 text-[10px] font-bold">
                <span className="text-blue-600">{patchStats.files} files</span>
                <span className="text-green-600">+{patchStats.added}</span>
                <span className="text-red-600">-{patchStats.removed}</span>
              </div>
            </div>
            <div className="p-4 overflow-y-auto font-mono text-xs text-gray-600 whitespace-pre">
              {patch || 'Waiting for agent to produce a patch...'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MonitorPage;
