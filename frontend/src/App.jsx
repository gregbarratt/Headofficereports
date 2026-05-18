import { Activity, Database, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { getApiHealth } from "./api/client.js";

const navItems = [
  "Dashboard",
  "Upload Centre",
  "Bookings",
  "Supplier Payments",
  "Customer Payments",
  "Trust Reconciliation",
  "Weekly Reports",
  "Settings",
];

function StatusCard({ icon: Icon, label, value, tone = "neutral" }) {
  return (
    <section className={`status-card status-card-${tone}`}>
      <Icon aria-hidden="true" size={20} />
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </section>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getApiHealth()
      .then((data) => {
        setHealth(data);
        setError("");
      })
      .catch(() => {
        setHealth(null);
        setError("Backend not connected");
      });
  }, []);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <ShieldCheck size={24} aria-hidden="true" />
          <div>
            <strong>Head Office</strong>
            <span>Reporting System</span>
          </div>
        </div>
        <nav aria-label="Main navigation">
          {navItems.map((item) => (
            <button key={item} type="button" disabled={item !== "Dashboard"}>
              {item}
            </button>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p>Phase 1</p>
            <h1>System Foundation</h1>
          </div>
          <span className={error ? "pill pill-error" : "pill pill-ok"}>
            {error || "Backend connected"}
          </span>
        </header>

        <div className="status-grid">
          <StatusCard
            icon={Activity}
            label="Backend"
            value={health?.status === "ok" ? "Healthy" : "Checking"}
            tone={health?.status === "ok" ? "success" : "neutral"}
          />
          <StatusCard
            icon={Database}
            label="Database"
            value={health?.database_configured ? "Configured" : "Not configured yet"}
          />
          <StatusCard
            icon={ShieldCheck}
            label="Access"
            value="Super Admin only"
            tone="success"
          />
        </div>

        <section className="panel">
          <h2>Build Progress</h2>
          <div className="progress-list">
            <span>FastAPI backend</span>
            <strong>Ready</strong>
            <span>React frontend</span>
            <strong>Ready</strong>
            <span>PostgreSQL settings</span>
            <strong>Ready for Phase 2</strong>
            <span>Agent portal features</span>
            <strong>Not included</strong>
          </div>
        </section>
      </section>
    </main>
  );
}
