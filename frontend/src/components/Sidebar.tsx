import { NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import { checkBackendHealth } from "../hooks/useApi";

const HEALTH_POLL_INTERVAL_MS = 15000;

const NAV_ITEMS = [
  { to: "/", label: "Run", icon: "▶" },
  { to: "/history", label: "History", icon: "📈" },
  { to: "/compare", label: "Compare", icon: "⇄" },
  { to: "/benchmark", label: "Benchmark", icon: "▦" },
  { to: "/flakiness", label: "Flakiness", icon: "◈" },
];

export function Sidebar() {
  const [connected, setConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const healthy = await checkBackendHealth();
      if (!cancelled) setConnected(healthy);
    };
    poll();
    const interval = setInterval(poll, HEALTH_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <aside className="w-56 shrink-0 h-screen sticky top-0 border-r border-border bg-card flex flex-col">
      <div className="px-5 py-5 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-accent flex items-center justify-center text-sm font-bold">
            A
          </div>
          <span className="font-semibold text-zinc-100 tracking-tight">Agenttest</span>
        </div>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-accent/15 text-accent font-medium"
                  : "text-zinc-400 hover:text-zinc-100 hover:bg-white/5"
              }`
            }
          >
            <span className="w-4 text-center">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-border flex items-center gap-2 text-xs text-zinc-500">
        <span
          className={`w-2 h-2 rounded-full ${
            connected === null ? "bg-zinc-600" : connected ? "bg-success" : "bg-failure"
          }`}
        />
        {connected === null ? "Checking..." : connected ? "Backend connected" : "Backend disconnected"}
      </div>
    </aside>
  );
}
