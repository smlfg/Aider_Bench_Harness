import React, { useEffect, useState } from 'react';
import { fetchPreflight } from '../lib/preflight';
import type { PreflightResult } from '../lib/preflight';
import { CheckCircle2, XCircle, Info, AlertTriangle, Activity, Database, Server, Cpu, Key, Zap, Microscope } from 'lucide-react';

const iconMap: Record<string, React.FC<{ size?: number; className?: string }>> = {
  docker: Server,
  swebench: Database,
  datasets: Cpu,
  aider: Activity,
  apikey: Key,
  litellm: Zap,
};

const pipelineSvgUrl = '/viz-static/pipeline.svg';
const experimentSvgUrl = '/viz-static/experiment.svg';

const InfoPage: React.FC = () => {
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPreflight()
      .then(setPreflight)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const checks = preflight
    ? Object.entries(preflight).map(([key, val]) => ({ key, ...val }))
    : [];

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-12">
      {/* Experiment Architecture */}
      <section>
        <div className="flex items-center justify-between gap-4 mb-4">
          <h2 className="text-xl font-bold text-gray-900">Versuchsaufbau</h2>
          <a
            href="/scientific-versuchsaufbau"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center space-x-2 px-3 py-2 rounded-lg border border-blue-200 bg-blue-50 text-sm font-semibold text-blue-700 hover:bg-blue-100"
          >
            <Microscope size={16} />
            <span>Wissenschaftlicher Modus</span>
          </a>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <img src={experimentSvgUrl} alt="Versuchsaufbau" className="w-full" />
        </div>
      </section>

      {/* Pipeline Architecture */}
      <section>
        <h2 className="text-xl font-bold text-gray-900 mb-4">Eval-Pipeline</h2>
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <img src={pipelineSvgUrl} alt="Eval-Pipeline" className="w-full" />
        </div>
      </section>

      {/* Preflight Checks */}
      <section>
        <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center space-x-2">
          <Info size={20} className="text-blue-600" />
          <span>Voraussetzungen</span>
        </h2>
        <p className="text-sm text-gray-500 mb-4">Live-Check der Infrastruktur beim Laden dieser Seite.</p>
        {loading && <p className="text-gray-400">Checking...</p>}
        {error && <p className="text-red-600">{error}</p>}
        {preflight && (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 text-left text-xs uppercase tracking-wider text-gray-500">
                  <th className="px-4 py-3">Komponente</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {checks.map(check => {
                  const Icon = iconMap[check.key] || Activity;
                  return (
                    <tr key={check.key} className="hover:bg-gray-50">
                      <td className="px-4 py-3 flex items-center space-x-2">
                        <Icon size={16} className="text-gray-400" />
                        <span className="font-medium text-gray-900">{check.label}</span>
                      </td>
                      <td className="px-4 py-3">
                        {check.ok ? (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-800">
                            <CheckCircle2 size={12} />
                            <span>OK</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800">
                            <XCircle size={12} />
                            <span>FAIL</span>
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 font-mono">{check.detail}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Details Cards */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="font-bold text-gray-900 mb-3 flex items-center space-x-2">
            <AlertTriangle size={16} className="text-amber-500" />
            <span><code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">--skip-eval</code></span>
          </h3>
          <ul className="text-sm text-gray-600 space-y-2">
            <li>Evaluierung wird übersprungen — kein Docker nötig</li>
            <li><code className="bg-gray-100 px-1 rounded">tests_total=0</code>, <code className="bg-gray-100 px-1 rounded">task_success=False</code></li>
            <li>Patch wird trotzdem gespeichert (<code className="bg-gray-100 px-1 rounded">git_diff.patch</code>)</li>
            <li>Eval kann nachträglich nachgeholt werden</li>
          </ul>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="font-bold text-gray-900 mb-3 flex items-center space-x-2">
            <Database size={16} className="text-purple-500" />
            <span>Judge</span>
          </h3>
          <ul className="text-sm text-gray-600 space-y-2">
            <li>Separater Schritt: <code className="bg-gray-100 px-1 rounded">harness-judge</code></li>
            <li>Bewertet Code-Qualität (Scope, Minimality, Clarity) je 1–5</li>
            <li>Braucht <code className="bg-gray-100 px-1 rounded">JUDGE_COMMAND</code> in <code className="bg-gray-100 px-1 rounded">.env</code></li>
            <li>Ohne Command: <code className="bg-gray-100 px-1 rounded">--allow-stub</code> → Neutral-Score 3.0</li>
          </ul>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="font-bold text-gray-900 mb-3 flex items-center space-x-2">
            <AlertTriangle size={16} className="text-red-500" />
            <span>Hinweise</span>
          </h3>
          <ul className="text-sm text-gray-600 space-y-2">
            <li><strong>Doppelter Eval-Bug:</strong> Normale Runs triggern eval zweimal (Cache verhindert Dopplung)</li>
            <li><strong><code>tokens_in = 0</code></strong> → Infrastructure Error</li>
            <li><strong><code>infrastructure_error = true</code></strong> → Run fließt nicht in Statistiken ein</li>
            <li><strong>Error-Detail:</strong> Konkreter Fehler-Snippet im Debrief sichtbar</li>
          </ul>
        </div>
      </section>
    </div>
  );
};

export default InfoPage;
