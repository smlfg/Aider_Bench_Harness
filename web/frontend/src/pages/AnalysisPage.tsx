import React, { useEffect, useState } from 'react';
import { fetchAnalysis, fetchComparisons } from '../lib/api';
import type { AnalysisRow, ComparisonRow } from '../lib/api';
import PlotFigure from '../components/PlotFigure';
import { AlertTriangle } from 'lucide-react';
import * as Plot from "@observablehq/plot";

const AnalysisPage: React.FC = () => {
  const [iterations, setIterations] = useState<number[]>([]);
  const [selectedIteration, setSelectedIteration] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisRow[]>([]);
  const [comparisons, setComparisons] = useState<ComparisonRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch('/api/completed-iterations')
      .then(r => r.json())
      .then(data => {
        setIterations(data);
        if (data.length > 0) setSelectedIteration(data[data.length - 1]);
      });
  }, []);

  useEffect(() => {
    if (selectedIteration === null) return;
    setLoading(true);
    Promise.all([
      fetchAnalysis(selectedIteration),
      fetchComparisons(selectedIteration)
    ]).then(([a, c]) => {
      setAnalysis(a);
      setComparisons(c);
      setLoading(false);
    });
  }, [selectedIteration]);

  const successComp = comparisons.find(c => c.metric === 'task_success');
  const diffComp = comparisons.find(c => c.metric === 'diff_size_loc');

  const isAiSlop = diffComp && successComp && 
    (diffComp.delta / (diffComp.baseline_estimate || 1) > 0.5) && 
    (successComp.delta <= 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Iteration Analysis</h2>
        <select 
          className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          value={selectedIteration || ''}
          onChange={(e) => setSelectedIteration(Number(e.target.value))}
        >
          {iterations.map(i => <option key={i} value={i}>Iteration {i}</option>)}
        </select>
      </div>

      {isAiSlop && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertTriangle className="h-5 w-5 text-red-400" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Warning: AI-Slop Detected</h3>
              <p className="text-sm text-red-700 mt-1">
                Diff size increased by {'>'}50% while task success remained flat or decreased. 
                The candidate is likely adding unnecessary code ("slop") without improving outcomes.
              </p>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <p>Loading...</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <h3 className="text-lg font-semibold mb-4 text-gray-800">Success Rate by Condition</h3>
            {analysis.filter(a => a.metric === 'task_success').length > 0 && (
              <PlotFigure options={{
                y: { grid: true, label: "Success Rate (%)", percent: true, domain: [0, 1] },
                x: { label: "Condition" },
                marks: [
                  Plot.barY(analysis.filter(a => a.metric === 'task_success'), {
                    x: "condition",
                    y: "point_estimate",
                    fill: "condition",
                    title: (d: any) => `${d.condition}: ${(d.point_estimate * 100).toFixed(1)}%`
                  }),
                  Plot.ruleY([0])
                ]
              }} />
            )}
          </div>

          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <h3 className="text-lg font-semibold mb-4 text-gray-800">Mean Diff Size (LoC)</h3>
            {analysis.filter(a => a.metric === 'diff_size_loc').length > 0 && (
              <PlotFigure options={{
                y: { grid: true, label: "LoC Added + Removed" },
                x: { label: "Condition" },
                marks: [
                  Plot.barY(analysis.filter(a => a.metric === 'diff_size_loc'), {
                    x: "condition",
                    y: "point_estimate",
                    fill: "condition"
                  }),
                  Plot.ruleY([0])
                ]
              }} />
            )}
          </div>

          <div className="lg:col-span-2 bg-white p-6 rounded-lg shadow-sm border border-gray-200 overflow-x-auto">
            <h3 className="text-lg font-semibold mb-4 text-gray-800">Statistical Comparisons (Candidate vs Baseline)</h3>
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Metric</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Baseline</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Candidate</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Delta</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">P-Value</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Significance</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {comparisons.map(c => (
                  <tr key={c.metric}>
                    <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">{c.metric}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">{c.baseline_estimate?.toFixed(2)}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">{c.candidate_estimate?.toFixed(2)}</td>
                    <td className={`px-4 py-2 whitespace-nowrap text-sm font-bold ${c.delta > 0 ? 'text-green-600' : c.delta < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                      {c.delta > 0 ? '+' : ''}{c.delta.toFixed(2)}
                    </td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">{c.p_value?.toFixed(4) || '-'}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm">
                      {c.p_value && c.p_value < 0.05 ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Significant</span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">NS</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisPage;
