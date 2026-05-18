import { Activity, Database, LockKeyhole, LogOut, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import {
  clearStoredToken,
  getApiHealth,
  getCurrentUser,
  getDashboardStatus,
  getStoredToken,
  loginSuperAdmin,
  logoutSuperAdmin,
  storeToken,
} from "./api/client.js";

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

function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const data = await loginSuperAdmin({ email, password });
      storeToken(data.access_token);
      onLogin(data.user, data.access_token);
    } catch (loginError) {
      setError(loginError.message || "Login failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-panel">
        <div className="login-brand">
          <ShieldCheck size={30} aria-hidden="true" />
          <div>
            <strong>Head Office</strong>
            <span>Reporting System</span>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <label>
            Email
            <input
              autoComplete="email"
              name="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>
          <label>
            Password
            <input
              autoComplete="current-password"
              name="password"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button className="primary-button" disabled={isSubmitting} type="submit">
            <LockKeyhole size={18} aria-hidden="true" />
            {isSubmitting ? "Signing in" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}

export default function App() {
  const [authChecked, setAuthChecked] = useState(false);
  const [token, setToken] = useState(() => getStoredToken());
  const [user, setUser] = useState(null);
  const [health, setHealth] = useState(null);
  const [dashboardStatus, setDashboardStatus] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      setAuthChecked(true);
      return;
    }

    getCurrentUser(token)
      .then((currentUser) => {
        setUser(currentUser);
        setAuthChecked(true);
      })
      .catch(() => {
        clearStoredToken();
        setToken(null);
        setUser(null);
        setAuthChecked(true);
      });
  }, [token]);

  useEffect(() => {
    if (!user || !token) {
      return;
    }

    getApiHealth()
      .then((data) => {
        setHealth(data);
        setError("");
      })
      .catch(() => {
        setHealth(null);
        setError("Backend not connected");
      });

    getDashboardStatus(token)
      .then((data) => setDashboardStatus(data))
      .catch((statusError) => setError(statusError.message || "Dashboard not connected"));
  }, [token, user]);

  function handleLogin(nextUser, nextToken) {
    setUser(nextUser);
    setToken(nextToken);
  }

  async function handleLogout() {
    try {
      if (token) {
        await logoutSuperAdmin(token);
      }
    } finally {
      clearStoredToken();
      setToken(null);
      setUser(null);
      setHealth(null);
      setDashboardStatus(null);
    }
  }

  if (!authChecked) {
    return (
      <main className="login-screen">
        <section className="login-panel">
          <div className="login-brand">
            <ShieldCheck size={30} aria-hidden="true" />
            <div>
              <strong>Head Office</strong>
              <span>Loading</span>
            </div>
          </div>
        </section>
      </main>
    );
  }

  if (!user || !token) {
    return <LoginPage onLogin={handleLogin} />;
  }

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
        <button className="logout-button" onClick={handleLogout} type="button">
          <LogOut size={18} aria-hidden="true" />
          Sign out
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p>{user.email}</p>
            <h1>Dashboard</h1>
          </div>
          <span className={error ? "pill pill-error" : "pill pill-ok"}>
            {error || dashboardStatus?.message || "Super Admin access confirmed"}
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
            <strong>Schema ready</strong>
            <span>Authentication</span>
            <strong>Super Admin only</strong>
            <span>Agent access</span>
            <strong>Not included</strong>
          </div>
        </section>
      </section>
    </main>
  );
}
