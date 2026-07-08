import { Route, Routes } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { RunView } from "./pages/RunView";
import { History } from "./pages/History";
import { Compare } from "./pages/Compare";
import { Benchmark } from "./pages/Benchmark";
import { Flakiness } from "./pages/Flakiness";

export default function App() {
  return (
    <div className="flex min-h-screen bg-bg text-zinc-100">
      <Sidebar />
      <main className="flex-1 px-8 py-8 max-w-6xl">
        <Routes>
          <Route path="/" element={<RunView />} />
          <Route path="/history" element={<History />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/benchmark" element={<Benchmark />} />
          <Route path="/flakiness" element={<Flakiness />} />
        </Routes>
      </main>
    </div>
  );
}
