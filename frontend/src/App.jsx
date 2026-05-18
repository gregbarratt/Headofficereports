import {
  Activity,
  Database,
  FileSpreadsheet,
  LockKeyhole,
  LogOut,
  Plane,
  ReceiptText,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  clearStoredToken,
  getApiHealth,
  getBookings,
  getCurrentUser,
  getDashboardStatus,
  getSupplierPayments,
  getStoredToken,
  getUploadBatches,
  getUploadTypes,
  loginSuperAdmin,
  logoutSuperAdmin,
  storeToken,
  uploadBatch,
} from "./api/client.js";

const navItems = [
  { label: "Dashboard", enabled: true },
  { label: "Upload Centre", enabled: true },
  { label: "Bookings", enabled: true },
  { label: "Supplier Payments", enabled: true },
  { label: "Customer Payments", enabled: false },
  { label: "Trust Reconciliation", enabled: false },
  { label: "Weekly Reports", enabled: false },
  { label: "Settings", enabled: false },
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

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(value));
}

function formatMoney(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
  }).format(Number(value));
}

function formatStatusLabel(value) {
  if (!value) {
    return "-";
  }
  return value.replaceAll("_", " ");
}

function UploadCentre({ token }) {
  const [uploadTypes, setUploadTypes] = useState([]);
  const [uploadType, setUploadType] = useState("");
  const [file, setFile] = useState(null);
  const [batches, setBatches] = useState([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  async function refreshBatches() {
    const nextBatches = await getUploadBatches(token);
    setBatches(nextBatches);
  }

  useEffect(() => {
    Promise.all([getUploadTypes(token), getUploadBatches(token)])
      .then(([types, nextBatches]) => {
        setUploadTypes(types);
        setUploadType(types[0]?.value || "");
        setBatches(nextBatches);
      })
      .catch((loadError) => setError(loadError.message || "Upload Centre could not load."));
  }, [token]);

  async function handleUpload(event) {
    event.preventDefault();
    setError("");
    setMessage("");

    if (!uploadType || !file) {
      setError("Choose an upload type and a file.");
      return;
    }

    setIsUploading(true);
    try {
      const batch = await uploadBatch({ token, uploadType, file });
      setMessage(`Upload batch ${batch.id} was validated with ${batch.accepted_rows} accepted rows.`);
      setFile(null);
      event.target.reset();
      await refreshBatches();
    } catch (uploadError) {
      setError(uploadError.message || "Upload failed.");
      await refreshBatches().catch(() => undefined);
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Upload Centre</h2>
          <p>Upload source files for validation and batch tracking.</p>
        </div>
        <FileSpreadsheet size={24} aria-hidden="true" />
      </div>

      <form className="upload-form" onSubmit={handleUpload}>
        <label>
          Upload type
          <select value={uploadType} onChange={(event) => setUploadType(event.target.value)} required>
            {uploadTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          File
          <input
            accept=".csv,.xlsx"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
            required
            type="file"
          />
        </label>
        <button className="primary-button" disabled={isUploading} type="submit">
          <Upload size={18} aria-hidden="true" />
          {isUploading ? "Uploading" : "Upload file"}
        </button>
      </form>

      {message ? <p className="form-success">{message}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Batch</th>
              <th>Type</th>
              <th>File</th>
              <th>Status</th>
              <th>Rows</th>
              <th>Accepted</th>
              <th>Rejected</th>
              <th>Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {batches.length ? (
              batches.map((batch) => (
                <tr key={batch.id}>
                  <td>{batch.id}</td>
                  <td>{batch.upload_type_label}</td>
                  <td>{batch.original_filename}</td>
                  <td>
                    <span className={`status-pill status-${batch.status}`}>{batch.status}</span>
                  </td>
                  <td>{batch.row_count}</td>
                  <td>{batch.accepted_rows}</td>
                  <td>{batch.rejected_rows}</td>
                  <td>{formatDateTime(batch.uploaded_at)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="8">No upload batches yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BookingsPage({ token }) {
  const [bookings, setBookings] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    getBookings(token)
      .then((data) => {
        setBookings(data.bookings);
        setTotal(data.total);
      })
      .catch((loadError) => setError(loadError.message || "Bookings could not load."));
  }, [token]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Bookings</h2>
          <p>{total} booking records</p>
        </div>
        <Plane size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Status</th>
              <th>Last Name</th>
              <th>Destination</th>
              <th>Departure</th>
              <th>Return</th>
              <th>Gross Value</th>
              <th>Supplier Nett</th>
              <th>ATOL</th>
            </tr>
          </thead>
          <tbody>
            {bookings.length ? (
              bookings.map((booking) => (
                <tr key={booking.id}>
                  <td>{booking.booking_ref}</td>
                  <td>{booking.normalised_status || "-"}</td>
                  <td>{booking.customer_last_name || "-"}</td>
                  <td>{booking.destination || "-"}</td>
                  <td>{formatDate(booking.departure_date)}</td>
                  <td>{formatDate(booking.return_date)}</td>
                  <td>{formatMoney(booking.gross_booking_value)}</td>
                  <td>{formatMoney(booking.expected_supplier_nett)}</td>
                  <td>{booking.atol_review_status || "-"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="9">No bookings imported yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SupplierPaymentsPage({ token }) {
  const [payments, setPayments] = useState([]);
  const [reconciliations, setReconciliations] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    getSupplierPayments(token)
      .then((data) => {
        setPayments(data.payments);
        setReconciliations(data.reconciliations);
        setTotal(data.total);
      })
      .catch((loadError) => setError(loadError.message || "Supplier payments could not load."));
  }, [token]);

  return (
    <section className="panel supplier-panel">
      <div className="panel-heading">
        <div>
          <h2>Supplier Payments</h2>
          <p>{total} imported supplier payment rows</p>
        </div>
        <ReceiptText size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="section-heading">
        <h3>Booking reconciliation</h3>
        <p>Expected supplier nett minus separately imported supplier payments.</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Last Name</th>
              <th>Expected Nett</th>
              <th>Total Paid</th>
              <th>Balance Due</th>
              <th>Variance</th>
              <th>Status</th>
              <th>Exception</th>
              <th>Trust</th>
              <th>True Profit</th>
            </tr>
          </thead>
          <tbody>
            {reconciliations.length ? (
              reconciliations.map((item) => (
                <tr key={item.booking_ref}>
                  <td>{item.booking_ref}</td>
                  <td>{item.customer_last_name || "-"}</td>
                  <td>{formatMoney(item.expected_supplier_nett)}</td>
                  <td>{formatMoney(item.supplier_payments_total)}</td>
                  <td>{formatMoney(item.supplier_balance_due)}</td>
                  <td>{formatMoney(item.supplier_variance)}</td>
                  <td>
                    <span className={`status-pill status-${item.supplier_reconciliation_status}`}>
                      {formatStatusLabel(item.supplier_reconciliation_status)}
                    </span>
                  </td>
                  <td>{item.supplier_exception || "None"}</td>
                  <td>{item.trust_status}</td>
                  <td>{item.true_profit_status}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="10">No bookings are ready for supplier reconciliation yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="section-heading">
        <h3>Imported payment rows</h3>
        <p>Each supplier payment line is stored separately.</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Booking Ref</th>
              <th>Product</th>
              <th>Supplier</th>
              <th>Payment Supplier</th>
              <th>Method</th>
              <th>Payment Value</th>
              <th>VAT</th>
              <th>Match</th>
              <th>Duplicate</th>
            </tr>
          </thead>
          <tbody>
            {payments.length ? (
              payments.map((payment) => (
                <tr key={payment.id}>
                  <td>{formatDate(payment.supplier_payment_date)}</td>
                  <td>{payment.booking_ref || "-"}</td>
                  <td>{payment.product_type || "-"}</td>
                  <td>{payment.supplier_name || "-"}</td>
                  <td>{payment.payment_supplier_name || "-"}</td>
                  <td>{payment.supplier_payment_method || "-"}</td>
                  <td>{formatMoney(payment.supplier_payment_amount)}</td>
                  <td>{formatMoney(payment.associated_vat)}</td>
                  <td>
                    <span className={`status-pill status-${payment.match_status}`}>
                      {formatStatusLabel(payment.match_status)}
                    </span>
                  </td>
                  <td>{payment.is_duplicate ? "Yes" : "No"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="10">No supplier payment rows imported yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function App() {
  const [authChecked, setAuthChecked] = useState(false);
  const [token, setToken] = useState(() => getStoredToken());
  const [user, setUser] = useState(null);
  const [health, setHealth] = useState(null);
  const [dashboardStatus, setDashboardStatus] = useState(null);
  const [activeView, setActiveView] = useState("Dashboard");
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
            <button
              className={activeView === item.label ? "nav-active" : ""}
              disabled={!item.enabled}
              key={item.label}
              onClick={() => setActiveView(item.label)}
              type="button"
            >
              {item.label}
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
            <h1>{activeView}</h1>
          </div>
          <span className={error ? "pill pill-error" : "pill pill-ok"}>
            {error || dashboardStatus?.message || "Super Admin access confirmed"}
          </span>
        </header>

        {activeView === "Upload Centre" ? (
          <UploadCentre token={token} />
        ) : activeView === "Bookings" ? (
          <BookingsPage token={token} />
        ) : activeView === "Supplier Payments" ? (
          <SupplierPaymentsPage token={token} />
        ) : (
          <>
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
                <span>Upload Centre</span>
                <strong>CSV/XLSX batch tracking</strong>
                <span>Supplier payments</span>
                <strong>Separate import and reconciliation</strong>
                <span>Agent access</span>
                <strong>Not included</strong>
              </div>
            </section>
          </>
        )}
      </section>
    </main>
  );
}
