import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import AnalysisPage from './pages/AnalysisPage';
import TrajectoryPage from './pages/TrajectoryPage';
import RunsPage from './pages/RunsPage';
import LaunchPage from './pages/LaunchPage';
import MonitorPage from './pages/MonitorPage';
import DebriefPage from './pages/DebriefPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<AnalysisPage />} />
          <Route path="trajectory" element={<TrajectoryPage />} />
          <Route path="runs" element={<RunsPage />} />
          <Route path="launch" element={<LaunchPage />} />
          <Route path="monitor/:runId" element={<MonitorPage />} />
          <Route path="debrief/:runId" element={<DebriefPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
