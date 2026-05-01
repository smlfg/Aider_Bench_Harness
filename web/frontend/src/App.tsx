import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import InfoPage from './pages/InfoPage';
import AnalysisPage from './pages/AnalysisPage';
import TrajectoryPage from './pages/TrajectoryPage';
import RunsPage from './pages/RunsPage';
import LaunchPage from './pages/LaunchPage';
import MonitorPage from './pages/MonitorPage';
import DebriefPage from './pages/DebriefPage';
import ExperimentPage from './pages/ExperimentPage';
import IncrementalPage from './pages/IncrementalPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<InfoPage />} />
          <Route path="analysis" element={<AnalysisPage />} />
          <Route path="trajectory" element={<TrajectoryPage />} />
          <Route path="runs" element={<RunsPage />} />
          <Route path="launch" element={<LaunchPage />} />
          <Route path="experiment" element={<ExperimentPage />} />
          <Route path="incremental" element={<IncrementalPage />} />
          <Route path="monitor/:runId" element={<MonitorPage />} />
          <Route path="debrief/:runId" element={<DebriefPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;