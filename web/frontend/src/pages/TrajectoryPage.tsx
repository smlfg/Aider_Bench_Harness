import React, { useEffect, useState } from 'react';
import { fetchTrajectory, TrajectoryRow } from '../lib/api';
import PlotFigure from '../components/PlotFigure';
import * as Plot from "@observablehq/plot";

const TrajectoryPage: React.FC = () => {
  const [data, setData] = useState<TrajectoryRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrajectory().then(d => {
      setData(d);
      setLoading(false);
    });
  }, []);

  if (loading) return <p>Loading...</p>;

  return (
    <div className="space-y-8">
      <h2 className="text-2xl font-bold text-gray-900">Experiment Trajectory</h2>

      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h3 className="text-lg font-semibold mb-4 text-gray-800">Pareto Frontier: Success vs Cost</h3>
        <p className="text-sm text-gray-500 mb-6">Lower diff size and higher success rate is better. Points on the frontier are optimal trade-offs.</p>
        <PlotFigure options={{
          grid: true,
          x: { label: "Mean Diff Size (LoC)" },
          y: { label: "Success Rate (%)", percent: true, domain: [0, 1] },
          marks: [
            Plot.dot(data, {
              x: "cumulative_diff_size_loc_mean",
              y: "cumulative_success_rate",
              stroke: (d: any) => d.pareto_dominated ? "#cbd5e1" : "#2563eb",
              fill: (d: any) => d.pareto_dominated ? "#f1f5f9" : "#dbeafe",
              r: 6,
              title: (d: any) => `Iteration ${d.iteration}\n${d.mutation_note}\nSuccess: ${(d.cumulative_success_rate * 100).toFixed(1)}%\nDiff: ${d.cumulative_diff_size_loc_mean.toFixed(1)} LoC`
            }),
            Plot.text(data, {
              x: "cumulative_diff_size_loc_mean",
              y: "cumulative_success_rate",
              text: (d: any) => d.iteration,
              dy: -12,
              fontSize: 10
            })
          ]
        }} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold mb-4 text-gray-800">Success Rate over Time</h3>
          <PlotFigure options={{
            grid: true,
            y: { label: "Success Rate (%)", percent: true, domain: [0, 1] },
            x: { label: "Iteration", tickFormat: "d" },
            marks: [
              Plot.lineY(data, { x: "iteration", y: "cumulative_success_rate", stroke: "#2563eb" }),
              Plot.dot(data, { x: "iteration", y: "cumulative_success_rate", fill: "#2563eb" })
            ]
          }} />
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold mb-4 text-gray-800">Diff Size over Time</h3>
          <PlotFigure options={{
            grid: true,
            y: { label: "LoC" },
            x: { label: "Iteration", tickFormat: "d" },
            marks: [
              Plot.lineY(data, { x: "iteration", y: "cumulative_diff_size_loc_mean", stroke: "#9333ea" }),
              Plot.dot(data, { x: "iteration", y: "cumulative_diff_size_loc_mean", fill: "#9333ea" })
            ]
          }} />
        </div>
      </div>
    </div>
  );
};

export default TrajectoryPage;
