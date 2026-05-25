import {
  Activity,
  AlertTriangle,
  Banknote,
  CheckCircle2,
  CircleAlert,
  Clock3,
  CreditCard,
  Database,
  FileSpreadsheet,
  HandCoins,
  Landmark,
  LockKeyhole,
  LogOut,
  Plane,
  ReceiptText,
  RefreshCw,
  Search,
  ShieldCheck,
  Upload,
  XCircle,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  allocateBankTransaction,
  allocateSupplierPayment,
  clearStoredToken,
  createManualTrustBalance,
  createEmailRecipient,
  downloadReportExcel,
  getAgentCommissions,
  getApiHealth,
  getBankTransactions,
  getBookingChecks,
  getBookings,
  getCurrentUser,
  getCustomerPayments,
  getDashboardStatus,
  getEmailRecipients,
  getExceptions,
  getHeadOfficeCosts,
  getInsuranceCosts,
  getRefunds,
  getReportRuns,
  getReportTypes,
  getSettingsStatus,
  getSupplierPayments,
  getStoredToken,
  getTrustReconciliation,
  getTraveltekUpdates,
  getTraveltekChangeLog,
  importTraveltekBookings,
  getUploadBatches,
  getUploadTypes,
  generateExceptions,
  generateWeeklySnapshot,
  getWeeklySnapshots,
  loginSuperAdmin,
  logoutSuperAdmin,
  onAuthExpired,
  runTraveltekActiveMaintenance,
  runTraveltekFullCatchUpBatch,
  runTraveltekUpdateEverythingBatch,
  scanNewTraveltekOtcReferences,
  sendWeeklyEmail,
  startFellohCustomerPaymentBackfill,
  storeToken,
  syncFellohCustomerPayments,
  syncTraveltekActiveBookings,
  updateBookingCheckAdjustments,
  updateEmailRecipient,
  updateExceptionStatus,
  updateTraveltekUpdateStatus,
  uploadBatch,
} from "./api/client.js";

const navItems = [
  { label: "Dashboard", enabled: true },
  { label: "Booking Checks", enabled: true },
  { label: "Upload Centre", enabled: true },
  { label: "Bookings", enabled: true },
  { label: "Traveltek Updates", enabled: true },
  { label: "Supplier Payments TAPs", enabled: true },
  { label: "Supplier Payments TT", enabled: true },
  { label: "Customer Payments", enabled: true },
  { label: "Insurance Costs", enabled: true },
  { label: "Refunds", enabled: true },
  { label: "Agent Commissions", enabled: true },
  { label: "Bank Transactions", enabled: true },
  { label: "Head Office Costs", enabled: true },
  { label: "Trust Reconciliation", enabled: true },
  { label: "Exceptions", enabled: true },
  { label: "Weekly Reports", enabled: true },
  { label: "Settings", enabled: true },
];

const FELLOH_CATCH_UP_START_DATE = "2023-01-01";
const TRAVELTEK_FULL_CATCH_UP_START_DATE = "2023-01-30";
const TRAVELTEK_ACTIVE_WINDOW_DAYS = 60;

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

function LoginPage({ notice = "", onLogin }) {
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
          {notice ? <p className="form-notice">{notice}</p> : null}
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

function textMatches(value, search) {
  const searchValue = search.trim().toLowerCase();
  if (!searchValue) {
    return true;
  }
  return String(value ?? "").toLowerCase().includes(searchValue);
}

function dateMatches(value, search) {
  return textMatches(value, search) || textMatches(formatDate(value), search);
}

function moneyMatches(value, search) {
  return textMatches(value, search) || textMatches(formatMoney(value), search);
}

function toDateInputValue(dateValue) {
  return dateValue.toISOString().slice(0, 10);
}

function toTimeInputValue(dateValue) {
  return `${String(dateValue.getHours()).padStart(2, "0")}:${String(dateValue.getMinutes()).padStart(2, "0")}`;
}

function defaultSyncStartDate() {
  const dateValue = new Date();
  dateValue.setDate(dateValue.getDate() - 30);
  return toDateInputValue(dateValue);
}

function isTraveltekNoRowsMessage(value) {
  return String(value || "").toLowerCase().includes("returned no booking rows");
}

function isLegacyTraveltekFieldMessage(value) {
  return /'(flight_included|accommodation_included|cruise_included|extras_included|package_included|normalised_status|atol_review_status)'/i.test(
    String(value || "")
  );
}

  function formatStatusLabel(value) {
    if (!value) {
      return "-";
    }
    return value.replaceAll("_", " ");
  }

  function redactSensitiveText(value) {
    if (!value) {
      return "";
    }
    return String(value)
      .replace(/(password\s*[=:]\s*)[^,\s|<>]+/gi, "$1[redacted]")
      .replace(/(username\s*[=:]\s*)[^,\s|<>]+/gi, "$1[redacted]")
      .replace(/(<auth\b[^>]*\bpassword=")[^"]+/gi, "$1[redacted]")
      .replace(/(<auth\b[^>]*\busername=")[^"]+/gi, "$1[redacted]");
  }

  function formatSourceLabel(value) {
  const labels = {
    taps: "TAPs",
    tt: "TT",
    sings: "SINGs",
    otc: "OTC",
    lemieux: "LeMieux",
    review: "Review",
  };
  return labels[value] || formatStatusLabel(value);
}

function ConfigStatus({ isConfigured, configuredLabel = "Configured", missingLabel = "Needs setting" }) {
  if (isConfigured === null || isConfigured === undefined) {
    return <span className="status-pill status-inactive">Loading</span>;
  }

  return (
    <span className={`status-pill ${isConfigured ? "status-active" : "status-incomplete"}`}>
      {isConfigured ? configuredLabel : missingLabel}
    </span>
  );
}

  function checkLabel(value) {
    const labels = {
      match: "Match",
      mismatch: "Mismatch",
      waiting_actual: "Awaiting actual",
      waiting_both: "Awaiting imports",
      waiting_human: "Awaiting Traveltek",
      waiting_master: "Awaiting Traveltek",
      waiting: "Awaiting imports",
    };
  return labels[value] || formatStatusLabel(value);
}

function CheckBadge({ status }) {
  const Icon = status === "match" ? CheckCircle2 : status === "mismatch" ? XCircle : Clock3;
  return (
    <span className={`status-pill status-${status}`}>
      <Icon size={15} aria-hidden="true" />
      {checkLabel(status)}
    </span>
  );
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
  const [bookingRefSort, setBookingRefSort] = useState("asc");

  useEffect(() => {
    getBookings(token, 10000)
      .then((data) => {
        setBookings(data.bookings);
        setTotal(data.total);
      })
      .catch((loadError) => setError(loadError.message || "Bookings could not load."));
  }, [token]);

  const sortedBookings = [...bookings].sort((left, right) => {
    const comparison = String(left.booking_ref || "").localeCompare(String(right.booking_ref || ""), undefined, {
      numeric: true,
      sensitivity: "base",
    });
    return bookingRefSort === "desc" ? -comparison : comparison;
  });

  function exportBookingsCsv() {
    const headers = [
      "Booking Ref",
      "Traveltek ID",
      "Company",
      "Status",
      "Customer / Lead",
      "Agent",
      "Destination",
      "Supplier Refs",
      "Departure",
      "Return",
      "Passenger Count",
      "Gross Value",
      "Supplier Nett",
      "ATOL",
      "Last Updated",
    ];
    const rows = sortedBookings.map((booking) => [
      booking.booking_ref,
      booking.traveltek_booking_id || "",
      formatSourceLabel(booking.booking_company),
      booking.normalised_status || "",
      booking.customer_last_name || "",
      booking.agent_in_charge || "",
      booking.destination || "",
      booking.supplier_references_raw || "",
      booking.departure_date || "",
      booking.return_date || "",
      booking.passenger_count ?? "",
      booking.gross_booking_value ?? "",
      booking.expected_supplier_nett ?? "",
      booking.atol_review_status || "",
      booking.updated_at || "",
    ]);
    downloadCsv("bookings.csv", headers, rows);
  }

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

      <div className="booking-page-actions">
        <label>
          Booking ref order
          <select value={bookingRefSort} onChange={(event) => setBookingRefSort(event.target.value)}>
            <option value="asc">Lowest to highest</option>
            <option value="desc">Highest to lowest</option>
          </select>
        </label>
        <button className="secondary-button" disabled={!sortedBookings.length} onClick={exportBookingsCsv} type="button">
          <FileSpreadsheet size={18} aria-hidden="true" />
          Download CSV
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Traveltek ID</th>
              <th>Company</th>
                <th>Status</th>
                <th>Customer / Lead</th>
                <th>Agent</th>
                <th>Destination</th>
                <th>Supplier refs</th>
                <th>Departure</th>
                <th>Return</th>
                <th>Passenger Count</th>
                <th>Gross Value</th>
                <th>Supplier Nett</th>
              <th>ATOL</th>
            </tr>
          </thead>
          <tbody>
            {sortedBookings.length ? (
              sortedBookings.map((booking) => (
                <tr key={booking.id}>
                  <td>{booking.booking_ref}</td>
                    <td>{booking.traveltek_booking_id || "-"}</td>
                    <td>{formatSourceLabel(booking.booking_company)}</td>
                    <td>{booking.normalised_status || "-"}</td>
                    <td>{booking.customer_last_name || "-"}</td>
                    <td>{booking.agent_in_charge || "-"}</td>
                    <td>{booking.destination || "-"}</td>
                    <td>{booking.supplier_references_raw || "-"}</td>
                    <td>{formatDate(booking.departure_date)}</td>
                    <td>{formatDate(booking.return_date)}</td>
                    <td>{booking.passenger_count ?? "-"}</td>
                    <td>{formatMoney(booking.gross_booking_value)}</td>
                  <td>{formatMoney(booking.expected_supplier_nett)}</td>
                  <td>{booking.atol_review_status || "-"}</td>
                </tr>
              ))
            ) : (
              <tr>
                  <td colSpan="14">No bookings imported yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function hasTraveltekReviewValue(value) {
  const text = value === null || value === undefined ? "" : String(value).trim();
  return text !== "" && text !== "-";
}

function traveltekSuggestionType(update) {
  const hasCurrent = hasTraveltekReviewValue(update.current_value);
  const hasTraveltek = hasTraveltekReviewValue(update.traveltek_value);

  if (!hasCurrent && hasTraveltek) {
    return "missing";
  }
  if (hasCurrent && hasTraveltek && String(update.current_value).trim() !== String(update.traveltek_value).trim()) {
    return "different";
  }
  if (hasCurrent && !hasTraveltek) {
    return "missing_traveltek";
  }
  return "review";
}

function traveltekSuggestionTypeLabel(type) {
  if (type === "missing") {
    return "Missing in our system";
  }
  if (type === "different") {
    return "Different value";
  }
  if (type === "missing_traveltek") {
    return "Traveltek value missing";
  }
  return "Needs review";
}

function groupTraveltekUpdatesByBooking(updates) {
  const groupsByRef = new Map();
  for (const update of updates) {
    const bookingRef = update.booking_ref || "Unknown booking";
    if (!groupsByRef.has(bookingRef)) {
      groupsByRef.set(bookingRef, {
        booking_ref: bookingRef,
        updates: [],
        missingFields: [],
        changedFields: [],
        keyDetails: {},
        newestDetectedAt: update.detected_at,
      });
    }

    const group = groupsByRef.get(bookingRef);
    group.updates.push(update);
    if (update.traveltek_key_details) {
      group.keyDetails = { ...group.keyDetails, ...update.traveltek_key_details };
    }
    if (!group.newestDetectedAt || update.detected_at > group.newestDetectedAt) {
      group.newestDetectedAt = update.detected_at;
    }

    const type = traveltekSuggestionType(update);
    if (type === "missing") {
      group.missingFields.push(update.field_label);
    }
    if (type === "different") {
      group.changedFields.push(update.field_label);
    }
  }

  return Array.from(groupsByRef.values()).sort((left, right) => {
    const leftDate = left.newestDetectedAt || "";
    const rightDate = right.newestDetectedAt || "";
    return rightDate.localeCompare(leftDate) || left.booking_ref.localeCompare(right.booking_ref);
  });
}

const traveltekKeyDetailLabels = [
  "Traveltek Booking ID",
  "Total Cost",
  "Total Amount Paid",
  "Outstanding",
  "Total Due",
  "Due to Suppliers",
  "Paid To Supplier",
  "Supplier References",
];

function traveltekKeyDetailValue(group, label) {
  const value = group.keyDetails?.[label];
  return hasTraveltekReviewValue(value) ? value : "-";
}

function traveltekChangeTypeLabel(changeType) {
  const labels = {
    created: "New booking",
    cancelled: "Cancelled",
    customer_payment_changed: "Customer payment changed",
    gross_value_changed: "Gross value changed",
    supplier_payment_changed: "Supplier payment changed",
    customer_balance_changed: "Customer balance changed",
    supplier_balance_changed: "Supplier balance changed",
    changed: "Booking changed",
  };
  return labels[changeType] || "Booking changed";
}

function traveltekChangeSummary(changes) {
  if (!changes?.length) {
    return "-";
  }
  return changes
    .slice(0, 4)
    .map((change) => `${change.field_label || change.field_name}: ${change.previous_value || "-"} -> ${change.new_value || "-"}`)
    .join("; ");
}

function TraveltekUpdatesPage({ token }) {
  const todayIso = new Date().toISOString().slice(0, 10);
  const defaultStartDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const defaultNewBookingStartDate = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const [updates, setUpdates] = useState([]);
  const [changeLog, setChangeLog] = useState([]);
  const [changeLogFilter, setChangeLogFilter] = useState("all");
  const [summary, setSummary] = useState(null);
  const [latestRun, setLatestRun] = useState(null);
  const [configured, setConfigured] = useState(false);
  const [statusFilter, setStatusFilter] = useState("open");
  const [syncLimit, setSyncLimit] = useState(25);
  const [importStartDate, setImportStartDate] = useState(defaultStartDate);
  const [importEndDate, setImportEndDate] = useState(todayIso);
  const [importLimit, setImportLimit] = useState(25);
  const [catchUpStartDate, setCatchUpStartDate] = useState(TRAVELTEK_FULL_CATCH_UP_START_DATE);
  const [catchUpEndDate, setCatchUpEndDate] = useState(todayIso);
  const [catchUpBatchDays, setCatchUpBatchDays] = useState(30);
  const [catchUpLimit, setCatchUpLimit] = useState(100);
  const [catchUpResetProgress, setCatchUpResetProgress] = useState(false);
  const [newBookingStartDate, setNewBookingStartDate] = useState(defaultNewBookingStartDate);
  const [newBookingEndDate, setNewBookingEndDate] = useState(todayIso);
  const [newBookingLimit, setNewBookingLimit] = useState(100);
  const [activeRefreshLimit, setActiveRefreshLimit] = useState(100);
  const [activeWindowDays, setActiveWindowDays] = useState(TRAVELTEK_ACTIVE_WINDOW_DAYS);
  const [newReferenceLimit, setNewReferenceLimit] = useState(25);
  const [newReferenceMissingStop, setNewReferenceMissingStop] = useState(10);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isScanningNewRefs, setIsScanningNewRefs] = useState(false);
  const [isCatchUpRunning, setIsCatchUpRunning] = useState(false);
  const [isAutoCatchUpRunning, setIsAutoCatchUpRunning] = useState(false);
  const [autoCatchUpStatus, setAutoCatchUpStatus] = useState("");
  const [autoCatchUpLog, setAutoCatchUpLog] = useState([]);
  const [autoCatchUpBatchesRun, setAutoCatchUpBatchesRun] = useState(0);
  const [autoCatchUpCallsUsed, setAutoCatchUpCallsUsed] = useState(0);
  const [isActiveMaintenanceRunning, setIsActiveMaintenanceRunning] = useState(false);
  const [updatingId, setUpdatingId] = useState(null);
  const [updatingGroupRef, setUpdatingGroupRef] = useState("");
  const [showAdvancedTraveltekTools, setShowAdvancedTraveltekTools] = useState(false);
  const stopAutoCatchUpRef = useRef(false);

  function catchUpRequestValues() {
    const batchDays = boundedNumber(catchUpBatchDays, 30, 1, 92);
    const limit = boundedNumber(catchUpLimit, 100, 1, 500);
    if (String(batchDays) !== String(catchUpBatchDays)) {
      setCatchUpBatchDays(batchDays);
    }
    if (String(limit) !== String(catchUpLimit)) {
      setCatchUpLimit(limit);
    }
    return { batchDays, limit };
  }

  function addAutoCatchUpLog(line) {
    setAutoCatchUpLog((currentLog) => [line, ...currentLog].slice(0, 10));
  }

  function normalisedCatchUpRunValues({ batchDays = catchUpBatchDays, limit = catchUpLimit } = {}) {
    return {
      batchDays: boundedNumber(batchDays, 30, 1, 92),
      limit: boundedNumber(limit, 100, 1, 500),
    };
  }

  function loadUpdates(nextStatus = statusFilter) {
    return getTraveltekUpdates(token, nextStatus)
      .then((data) => {
        setUpdates(data.updates || []);
        setSummary(data.summary);
        setLatestRun(data.latest_run);
        setConfigured(data.configured);
        setError("");
      })
      .catch((loadError) => setError(loadError.message || "Traveltek updates could not load."));
  }

  function loadChangeLog(nextChangeType = changeLogFilter) {
    return getTraveltekChangeLog(token, nextChangeType, 100)
      .then((rows) => setChangeLog(rows || []))
      .catch((loadError) => setError(loadError.message || "Traveltek change log could not load."));
  }

  async function refreshTraveltekPage(nextStatus = statusFilter, nextChangeType = changeLogFilter) {
    await Promise.all([loadUpdates(nextStatus), loadChangeLog(nextChangeType)]);
  }

  useEffect(() => {
    refreshTraveltekPage(statusFilter, changeLogFilter);
  }, [token, statusFilter, changeLogFilter]);

  async function handleSync() {
    setIsSyncing(true);
    setMessage("");
    setError("");
      try {
        const run = await syncTraveltekActiveBookings({ token, limit: Number(syncLimit) });
        setMessage(
          `Traveltek review refresh finished. Traveltek calls attempted: ${run.api_call_count}. Successfully checked: ${run.checked_bookings}. Suggestions created: ${run.proposals_created}.`
          );
          if (run.error_summary) {
            setError(`Traveltek returned an issue: ${redactSensitiveText(run.error_summary)}`);
          }
        await refreshTraveltekPage(statusFilter, changeLogFilter);
      } catch (syncError) {
        setError(syncError.message || "Traveltek check could not run.");
    } finally {
      setIsSyncing(false);
    }
  }

  async function handleBookingImport() {
    setIsImporting(true);
    setMessage("");
    setError("");
    try {
      const run = await importTraveltekBookings({
          token,
          startDate: importStartDate,
          endDate: importEndDate,
          limit: Number(importLimit),
        });
      setMessage(
          `Traveltek import finished. API calls attempted: ${run.api_call_count}. Booking records checked: ${run.checked_bookings}. New or changed bookings: ${run.proposals_created}.`
        );
        if (run.error_summary) {
          const safeSummary = redactSensitiveText(run.error_summary);
          if (isTraveltekNoRowsMessage(safeSummary)) {
            setMessage(
              `Traveltek import finished. No booking rows were returned for ${formatDate(importStartDate)} to ${formatDate(importEndDate)}. Try a wider booking-date range if needed.`
            );
          } else {
            setError(`Traveltek returned an issue: ${safeSummary}`);
          }
        }
      await refreshTraveltekPage(statusFilter, changeLogFilter);
    } catch (importError) {
      setError(importError.message || "Traveltek booking import could not run.");
    } finally {
      setIsImporting(false);
    }
  }

  async function handleFullCatchUpBatch() {
    setIsCatchUpRunning(true);
    setMessage("");
    setError("");
    try {
      const { batchDays, limit } = catchUpRequestValues();
      const result = await runTraveltekFullCatchUpBatch({
        token,
        startDate: catchUpStartDate,
        endDate: catchUpEndDate,
        batchDays,
        limit,
        resetProgress: catchUpResetProgress,
      });
      if (result.complete && !result.run) {
        setMessage(result.message);
      } else {
        const nextText = result.complete
          ? "Full catch-up is complete."
          : `Next batch starts ${formatDate(result.next_start_date)}.`;
        setMessage(
          `Full catch-up batch finished: ${formatDate(result.batch_start_date)} to ${formatDate(result.batch_end_date)}. ` +
            `API calls attempted: ${result.run?.api_call_count ?? 0}. Booking records checked: ${result.run?.checked_bookings ?? 0}. ` +
            `New or changed bookings: ${result.run?.proposals_created ?? 0}. ${nextText}`
        );
        if (result.run?.error_summary) {
          setError(`Traveltek returned an issue: ${redactSensitiveText(result.run.error_summary)}`);
        }
      }
      setCatchUpResetProgress(false);
      await refreshTraveltekPage(statusFilter, changeLogFilter);
    } catch (catchUpError) {
      setError(catchUpError.message || "Traveltek full catch-up batch could not run.");
    } finally {
      setIsCatchUpRunning(false);
    }
  }

  async function runAutomaticCatchUp({
    startDate = catchUpStartDate,
    endDate = catchUpEndDate,
    batchDays: requestedBatchDays = catchUpBatchDays,
    limit: requestedLimit = catchUpLimit,
    resetProgress = catchUpResetProgress,
    startMessage = "Automatic catch-up started.",
  } = {}) {
    const { batchDays, limit } = normalisedCatchUpRunValues({
      batchDays: requestedBatchDays,
      limit: requestedLimit,
    });
    setIsAutoCatchUpRunning(true);
    stopAutoCatchUpRef.current = false;
    setMessage("");
    setError("");
    setAutoCatchUpStatus(startMessage);
    setAutoCatchUpLog([]);
    setAutoCatchUpBatchesRun(0);
    setAutoCatchUpCallsUsed(0);

    let batchesRun = 0;
    let callsUsed = 0;
    let stoppedForError = false;
    let resetProgressOnNextBatch = resetProgress;
    const safetyBatchLimit = 1500;

    try {
      while (!stopAutoCatchUpRef.current) {
        const result = await runTraveltekFullCatchUpBatch({
          token,
          startDate,
          endDate,
          batchDays,
          limit,
          resetProgress: resetProgressOnNextBatch,
        });
        resetProgressOnNextBatch = false;
        setCatchUpResetProgress(false);

        if (!result.run && result.complete) {
          setMessage(result.message);
          setAutoCatchUpStatus("Automatic catch-up complete.");
          break;
        }

        batchesRun += result.run ? 1 : 0;
        callsUsed += result.run?.api_call_count ?? 0;
        setAutoCatchUpBatchesRun(batchesRun);
        setAutoCatchUpCallsUsed(callsUsed);
        setAutoCatchUpStatus(
          result.complete
            ? "Automatic catch-up complete."
            : `Last batch: ${formatDate(result.batch_start_date)} to ${formatDate(result.batch_end_date)}. Next batch starts ${formatDate(result.next_start_date)}.`
        );
        addAutoCatchUpLog(
          `${formatDate(result.batch_start_date)} to ${formatDate(result.batch_end_date)}: checked ${result.run?.checked_bookings ?? 0}, changed ${result.run?.proposals_created ?? 0}, calls ${result.run?.api_call_count ?? 0}.`
        );

        if (result.run?.status === "failed") {
          setError(`Automatic catch-up stopped because Traveltek returned an issue: ${redactSensitiveText(result.run.error_summary || "")}`);
          break;
        }

        if (result.complete) {
          setMessage(
            `Automatic catch-up complete. Batches run: ${batchesRun}. Traveltek calls used: ${callsUsed}.`
          );
          break;
        }

        if (batchesRun >= safetyBatchLimit) {
          setError("Automatic catch-up paused at the safety limit. Start it again to continue from the saved next date.");
          break;
        }

        await wait(800);
      }

      if (stopAutoCatchUpRef.current) {
        setMessage(`Automatic catch-up stopped. Batches run: ${batchesRun}. Traveltek calls used: ${callsUsed}.`);
      }

      await refreshTraveltekPage(statusFilter, changeLogFilter);
    } catch (catchUpError) {
      setError(catchUpError.message || "Automatic Traveltek catch-up could not continue.");
    } finally {
      setIsAutoCatchUpRunning(false);
    }
  }

  function handleAutoFullCatchUp() {
    return runAutomaticCatchUp();
  }

  async function runUpdateEverythingExistingBookings({ limit = 25, resetProgress = false } = {}) {
    const safeLimit = boundedNumber(limit, 25, 1, 500);
    setIsAutoCatchUpRunning(true);
    stopAutoCatchUpRef.current = false;
    setMessage("");
    setError("");
    setAutoCatchUpStatus("Update everything started. Existing bookings are being refreshed from Traveltek by booking reference.");
    setAutoCatchUpLog([]);
    setAutoCatchUpBatchesRun(0);
    setAutoCatchUpCallsUsed(0);

    let batchesRun = 0;
    let callsUsed = 0;
    let resetProgressOnNextBatch = resetProgress;
    let stoppedForError = false;
    const safetyBatchLimit = 1000;

    try {
      while (!stopAutoCatchUpRef.current) {
        const result = await runTraveltekUpdateEverythingBatch({
          token,
          limit: safeLimit,
          resetProgress: resetProgressOnNextBatch,
        });
        resetProgressOnNextBatch = false;

        batchesRun += result.run ? 1 : 0;
        callsUsed += result.run?.api_call_count ?? 0;
        setAutoCatchUpBatchesRun(batchesRun);
        setAutoCatchUpCallsUsed(callsUsed);
        addAutoCatchUpLog(
          `Existing bookings: checked ${result.run?.checked_bookings ?? 0}, changed ${result.run?.proposals_created ?? 0}, calls ${result.run?.api_call_count ?? 0}.`
        );
        setAutoCatchUpStatus(
          result.complete
            ? "Update everything complete."
            : `Refreshing existing bookings. Next batch continues after ${result.next_booking_ref || "the last checked booking"}.`
        );

        if (result.run?.status === "failed") {
          setError(`Update everything stopped because Traveltek returned an issue: ${redactSensitiveText(result.run.error_summary || "Unknown Traveltek error.")}`);
          stoppedForError = true;
          break;
        }

        if (result.run?.error_summary) {
          setError(`Traveltek returned an issue on this batch: ${redactSensitiveText(result.run.error_summary)}`);
        }

        if (result.complete) {
          setMessage(result.message || `Update everything complete. Batches run: ${batchesRun}. Traveltek calls used: ${callsUsed}.`);
          break;
        }

        if (batchesRun >= safetyBatchLimit) {
          setError("Update everything paused at the safety limit. Press the button again to continue from where it stopped.");
          stoppedForError = true;
          break;
        }

        await wait(900);
      }

      if (stopAutoCatchUpRef.current) {
        setMessage(`Update everything stopped. Batches run: ${batchesRun}. Traveltek calls used: ${callsUsed}.`);
      } else if (!stoppedForError) {
        setMessage(`Update everything complete. Batches run: ${batchesRun}. Traveltek calls used: ${callsUsed}.`);
        setAutoCatchUpStatus("Update everything complete.");
      }

      await refreshTraveltekPage(statusFilter, changeLogFilter);
    } catch (updateError) {
      setError(updateError.message || "Update everything could not continue.");
    } finally {
      setIsAutoCatchUpRunning(false);
    }
  }

  function handleUpdateEverything() {
    return runUpdateEverythingExistingBookings({
      limit: 25,
      resetProgress: false,
    });
  }

  function stopAutoFullCatchUp() {
    stopAutoCatchUpRef.current = true;
    setAutoCatchUpStatus("Stopping after the current batch finishes.");
  }

  async function handleActiveMaintenance() {
    setIsActiveMaintenanceRunning(true);
    setMessage("");
    setError("");
    try {
      const result = await runTraveltekActiveMaintenance({
        token,
        newBookingStartDate,
        newBookingEndDate,
        newBookingLimit: Number(newBookingLimit),
        refreshLimit: Number(activeRefreshLimit),
        activeWindowDays: Number(activeWindowDays),
      });
      setMessage(
        `Active update finished. New-booking import used ${result.new_booking_run.api_call_count} call(s) and checked ${result.new_booking_run.checked_bookings} booking(s). ` +
          `Active refresh used ${result.refresh_run.api_call_count} call(s) and checked ${result.refresh_run.checked_bookings} booking(s). ` +
          `Only bookings departing from ${formatDate(result.active_window_start_date)} onwards, plus blank departure dates, were refreshed.`
      );
      const issues = [result.new_booking_run.error_summary, result.refresh_run.error_summary].filter(Boolean);
      if (issues.length) {
        setError(`Traveltek returned an issue: ${redactSensitiveText(issues.join(" "))}`);
      }
      await refreshTraveltekPage(statusFilter, changeLogFilter);
    } catch (maintenanceError) {
      setError(maintenanceError.message || "Traveltek active update could not run.");
    } finally {
      setIsActiveMaintenanceRunning(false);
    }
  }

  async function handleNewReferenceScan() {
    setIsScanningNewRefs(true);
    setMessage("");
    setError("");
    try {
      const result = await scanNewTraveltekOtcReferences({
        token,
        maxReferences: Number(newReferenceLimit),
        stopAfterMissing: Number(newReferenceMissingStop),
      });
      setMessage(
        `${result.message} Checked ${result.first_checked_booking_ref || "-"} to ${result.last_checked_booking_ref || "-"}. Traveltek calls used: ${result.run.api_call_count}.`
      );
      if (result.run.error_summary) {
        setError(redactSensitiveText(result.run.error_summary));
      }
      await refreshTraveltekPage(statusFilter, changeLogFilter);
    } catch (scanError) {
      setError(scanError.message || "Traveltek new reference scan could not run.");
    } finally {
      setIsScanningNewRefs(false);
    }
  }

  async function handleStatusChange(updateId, nextStatus) {
    setUpdatingId(updateId);
    setMessage("");
    setError("");
    try {
      await updateTraveltekUpdateStatus({ token, updateId, status: nextStatus });
      setMessage(
        nextStatus === "resolved"
          ? "Traveltek suggestion applied to the booking."
          : `Traveltek suggestion marked as ${formatStatusLabel(nextStatus)}.`
      );
      await refreshTraveltekPage(statusFilter, changeLogFilter);
    } catch (updateError) {
      setError(updateError.message || "Traveltek suggestion could not be updated.");
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleGroupStatusChange(group, nextStatus) {
    setUpdatingGroupRef(group.booking_ref);
    setMessage("");
    setError("");
    try {
      const updatesToChange = group.updates.filter((update) => update.status !== nextStatus);
      await Promise.all(
        updatesToChange.map((update) => updateTraveltekUpdateStatus({ token, updateId: update.id, status: nextStatus }))
      );
      setMessage(
        nextStatus === "resolved"
          ? `${group.booking_ref} suggestions applied to the booking.`
          : `${group.booking_ref} suggestions marked as ${formatStatusLabel(nextStatus)}.`
      );
      await refreshTraveltekPage(statusFilter, changeLogFilter);
    } catch (updateError) {
      setError(updateError.message || "Traveltek suggestions could not be updated.");
    } finally {
      setUpdatingGroupRef("");
    }
  }

  const groupedUpdates = groupTraveltekUpdatesByBooking(updates);
  const safeCatchUpLimit = boundedNumber(catchUpLimit, 100, 1, 500);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Traveltek Updates</h2>
          <p>Pulls booking data from Traveltek and groups suggested changes for review.</p>
        </div>
        <RefreshCw size={24} aria-hidden="true" />
      </div>

      {message ? <p className="form-success">{message}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
        {!configured ? (
          <p className="form-error">Traveltek API is not configured yet. Add the Traveltek username, password and sitename / SID in Render.</p>
        ) : null}

      <div className="summary-strip summary-strip-wide">
        <div>
          <span>Open suggestions</span>
          <strong>{summary?.open_count ?? 0}</strong>
        </div>
        <div>
          <span>Reviewing</span>
          <strong>{summary?.reviewing_count ?? 0}</strong>
        </div>
        <div>
          <span>Applied</span>
          <strong>{summary?.resolved_count ?? 0}</strong>
        </div>
        <div>
          <span>Ignored</span>
          <strong>{summary?.ignored_count ?? 0}</strong>
        </div>
          <div>
            <span>Last check</span>
            <strong>{latestRun ? formatDateTime(latestRun.started_at) : "-"}</strong>
          </div>
          <div>
            <span>Last Traveltek status</span>
            <strong>{latestRun ? formatStatusLabel(latestRun.status) : "-"}</strong>
          </div>
        </div>

        {latestRun?.error_summary ? (
          isTraveltekNoRowsMessage(latestRun.error_summary) ? (
            <p className="muted-note">Last Traveltek note: {redactSensitiveText(latestRun.error_summary)}</p>
          ) : isLegacyTraveltekFieldMessage(latestRun.error_summary) ? (
            <p className="muted-note">Last Traveltek note: older internal-field suggestions are now hidden.</p>
          ) : (
            <p className="form-error">Last Traveltek issue: {redactSensitiveText(latestRun.error_summary)}</p>
          )
        ) : null}

        <div className="section-heading">
          <h3>Find new OTC bookings</h3>
          <p>Checks only the next OTC references after the highest booking already in this system.</p>
        </div>
        <div className="traveltek-toolbar">
          <label>
            References to check
            <input
              max="200"
              min="1"
              onChange={(event) => setNewReferenceLimit(event.target.value)}
              type="number"
              value={newReferenceLimit}
            />
          </label>
          <label>
            Stop after missing
            <input
              max="50"
              min="1"
              onChange={(event) => setNewReferenceMissingStop(event.target.value)}
              type="number"
              value={newReferenceMissingStop}
            />
          </label>
          <button className="primary-button" disabled={isScanningNewRefs || !configured} onClick={handleNewReferenceScan} type="button">
            <RefreshCw size={18} aria-hidden="true" />
            {isScanningNewRefs ? "Checking" : "Find New OTC Bookings"}
          </button>
        </div>
        <p className="muted-note">
          Example: if the last booking is OTC-06677, this checks OTC-06678 onward and imports any new bookings Traveltek returns.
        </p>

        <div className="traveltek-simple-update">
          <div>
            <h3>Update Everything</h3>
            <p>
              Refreshes the bookings already in this system using each booking reference or Traveltek ID.
            </p>
          </div>
          {isAutoCatchUpRunning ? (
            <button className="secondary-button" onClick={stopAutoFullCatchUp} type="button">
              Stop Updating
            </button>
          ) : (
            <button className="primary-button" disabled={isCatchUpRunning || !configured} onClick={handleUpdateEverything} type="button">
              <RefreshCw size={18} aria-hidden="true" />
              Update Everything From Traveltek
            </button>
          )}
        </div>

        <div className="traveltek-advanced-toggle">
          <button className="secondary-button" onClick={() => setShowAdvancedTraveltekTools((isShown) => !isShown)} type="button">
            {showAdvancedTraveltekTools ? "Hide advanced tools" : "Show advanced tools"}
          </button>
          <p className="muted-note">Advanced tools are backup date-search options. Day-to-day work should use Find New OTC Bookings and Update Everything.</p>
        </div>

        {showAdvancedTraveltekTools ? (
          <div className="traveltek-advanced-panel">
            <div className="section-heading">
              <h3>Advanced catch-up controls</h3>
              <p>Use these only when you want to change the catch-up dates, batch size or restart position.</p>
            </div>
            <div className="traveltek-toolbar">
              <label>
                Catch-up from
                <input
                  onChange={(event) => setCatchUpStartDate(event.target.value)}
                  type="date"
                  value={catchUpStartDate}
                />
              </label>
              <label>
                Catch-up to
                <input
                  onChange={(event) => setCatchUpEndDate(event.target.value)}
                  type="date"
                  value={catchUpEndDate}
                />
              </label>
              <label>
                Days per batch
                <input
                  max="92"
                  min="1"
                  onChange={(event) => setCatchUpBatchDays(event.target.value)}
                  type="number"
                  value={catchUpBatchDays}
                />
              </label>
              <label>
                Max bookings
                <input
                  max="500"
                  min="1"
                  onChange={(event) => setCatchUpLimit(event.target.value)}
                  type="number"
                  value={catchUpLimit}
                />
              </label>
              <label className="checkbox-label">
                <input
                  checked={catchUpResetProgress}
                  onChange={(event) => setCatchUpResetProgress(event.target.checked)}
                  type="checkbox"
                />
                Start again from catch-up from date
              </label>
              <button className="primary-button" disabled={isCatchUpRunning || isAutoCatchUpRunning || !configured} onClick={handleFullCatchUpBatch} type="button">
                <RefreshCw size={18} aria-hidden="true" />
                {isCatchUpRunning ? "Running batch" : "Run Next Catch-up Batch"}
              </button>
              {isAutoCatchUpRunning ? (
                <button className="secondary-button" disabled type="button">
                  Traveltek update running
                </button>
              ) : (
                <button className="primary-button" disabled={isCatchUpRunning || !configured} onClick={handleAutoFullCatchUp} type="button">
                  <RefreshCw size={18} aria-hidden="true" />
                  Start Automatic Catch-up
                </button>
              )}
            </div>
            <p className="muted-note">
              Estimated calls for each batch: up to {safeCatchUpLimit + 1}. Max bookings is 500 per batch. Automatic catch-up keeps running the next saved batch until complete, but this page must stay open.
            </p>
            {autoCatchUpStatus ? (
              <p className="muted-note">
                {autoCatchUpStatus} Batches run: {autoCatchUpBatchesRun}. Calls used: {autoCatchUpCallsUsed}.
              </p>
            ) : null}
            {autoCatchUpLog.length ? (
              <div className="traveltek-update-log">
                <strong>Latest batches</strong>
                <ul>
                  {autoCatchUpLog.map((line, index) => (
                    <li key={`${line}-${index}`}>{line}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="section-heading">
              <h3>Ongoing active update</h3>
              <p>Pulls recent new bookings, then refreshes only bookings inside the active departure window.</p>
            </div>
            <div className="traveltek-toolbar">
              <label>
                New bookings from
                <input
                  onChange={(event) => setNewBookingStartDate(event.target.value)}
                  type="date"
                  value={newBookingStartDate}
                />
              </label>
              <label>
                New bookings to
                <input
                  onChange={(event) => setNewBookingEndDate(event.target.value)}
                  type="date"
                  value={newBookingEndDate}
                />
              </label>
              <label>
                New booking limit
                <input
                  max="500"
                  min="1"
                  onChange={(event) => setNewBookingLimit(event.target.value)}
                  type="number"
                  value={newBookingLimit}
                />
              </label>
              <label>
                Active refresh limit
                <input
                  max="500"
                  min="1"
                  onChange={(event) => setActiveRefreshLimit(event.target.value)}
                  type="number"
                  value={activeRefreshLimit}
                />
              </label>
              <label>
                Days after departure
                <input
                  max="365"
                  min="1"
                  onChange={(event) => setActiveWindowDays(event.target.value)}
                  type="number"
                  value={activeWindowDays}
                />
              </label>
              <button className="primary-button" disabled={isActiveMaintenanceRunning || !configured} onClick={handleActiveMaintenance} type="button">
                <RefreshCw size={18} aria-hidden="true" />
                {isActiveMaintenanceRunning ? "Updating" : "Run Active Update"}
              </button>
            </div>
            <p className="muted-note">
              Estimated calls: up to {Number(newBookingLimit || 0) + Number(activeRefreshLimit || 0) + 1}. With the default 60 days, old departed bookings are skipped unless you pull them manually.
            </p>

            <div className="section-heading">
              <h3>Manual one-off pull</h3>
            </div>
            <div className="traveltek-toolbar">
              <label>
                Booking date from
                <input
                  onChange={(event) => setImportStartDate(event.target.value)}
                  type="date"
                  value={importStartDate}
                />
              </label>
              <label>
                Booking date to
                <input
                  onChange={(event) => setImportEndDate(event.target.value)}
                  type="date"
                  value={importEndDate}
                />
              </label>
              <label>
                Max bookings
                <input
                  max="500"
                  min="1"
                  onChange={(event) => setImportLimit(event.target.value)}
                  type="number"
                  value={importLimit}
                />
              </label>
              <button className="primary-button" disabled={isImporting || !configured} onClick={handleBookingImport} type="button">
                <RefreshCw size={18} aria-hidden="true" />
                {isImporting ? "Pulling" : "Pull Bookings From Traveltek"}
              </button>
            </div>
          </div>
        ) : null}

        <div className="section-heading">
          <h3>Booking change log</h3>
          <p>Shows what Traveltek changed on bookings after an import or refresh.</p>
        </div>
        <div className="traveltek-toolbar">
          <label>
            Change type
            <select value={changeLogFilter} onChange={(event) => setChangeLogFilter(event.target.value)}>
              <option value="all">All changes</option>
              <option value="cancelled">Cancelled bookings</option>
              <option value="changed">Changed bookings</option>
              <option value="created">New bookings</option>
            </select>
          </label>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Detected</th>
                <th>Booking ref</th>
                <th>Change</th>
                <th>Fields changed</th>
                <th>Before and after</th>
              </tr>
            </thead>
            <tbody>
              {changeLog.length ? (
                changeLog.map((row) => (
                  <tr key={row.id}>
                    <td>{formatDateTime(row.created_at)}</td>
                    <td>{row.booking_ref || "-"}</td>
                    <td>
                      <span className={`status-pill status-${row.change_type === "cancelled" ? "mismatch" : "reviewing"}`}>
                        {traveltekChangeTypeLabel(row.change_type)}
                      </span>
                    </td>
                    <td>{row.changed_fields?.length ? row.changed_fields.join(", ") : "-"}</td>
                    <td>{traveltekChangeSummary(row.changes)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5">No Traveltek booking changes logged yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="section-heading">
          <h3>Review suggestions</h3>
        </div>
        <div className="traveltek-toolbar">
          <label>
            Suggestions
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="open">Open</option>
            <option value="reviewing">Reviewing</option>
            <option value="resolved">Applied</option>
            <option value="ignored">Ignored</option>
            <option value="all">All</option>
          </select>
        </label>
        <label>
          Bookings to refresh
          <input
            max="500"
            min="1"
            onChange={(event) => setSyncLimit(event.target.value)}
            type="number"
            value={syncLimit}
          />
        </label>
        <button className="primary-button" disabled={isSyncing || !configured} onClick={handleSync} type="button">
          <RefreshCw size={18} aria-hidden="true" />
          {isSyncing ? "Refreshing" : "Refresh Suggestions"}
        </button>
      </div>

      <p className="muted-note">
        Suggestions are shown below by booking reference.
      </p>

      {groupedUpdates.length ? (
        <div className="traveltek-booking-groups">
          {groupedUpdates.map((group) => (
            <section className="traveltek-booking-group" key={group.booking_ref}>
              <div className="traveltek-booking-group-heading">
                <div>
                  <h3>{group.booking_ref}</h3>
                  <p>
                    {group.updates.length} field(s) need checking.{" "}
                    {group.missingFields.length ? `${group.missingFields.length} missing in our system.` : "No missing system fields."}{" "}
                    {group.changedFields.length ? `${group.changedFields.length} different value(s).` : ""}
                  </p>
                </div>
                <div className="table-actions">
                  <button
                    disabled={updatingGroupRef === group.booking_ref}
                    onClick={() => handleGroupStatusChange(group, "reviewing")}
                    type="button"
                  >
                    Review all
                  </button>
                  <button
                    disabled={updatingGroupRef === group.booking_ref}
                    onClick={() => handleGroupStatusChange(group, "resolved")}
                    type="button"
                  >
                    Apply all
                  </button>
                  <button
                    disabled={updatingGroupRef === group.booking_ref}
                    onClick={() => handleGroupStatusChange(group, "ignored")}
                    type="button"
                  >
                    Ignore all
                  </button>
                </div>
              </div>

              <div className="traveltek-booking-needs">
                <div>
                  <span>Missing in our system</span>
                  <strong>{group.missingFields.length ? group.missingFields.join(", ") : "None"}</strong>
                </div>
                <div>
                  <span>Different values</span>
                  <strong>{group.changedFields.length ? group.changedFields.join(", ") : "None"}</strong>
                </div>
              </div>

              <div className="traveltek-key-details">
                {traveltekKeyDetailLabels.map((label) => (
                  <div key={`${group.booking_ref}-${label}`}>
                    <span>{label}</span>
                    <strong>{traveltekKeyDetailValue(group, label)}</strong>
                  </div>
                ))}
              </div>

              <div className="table-wrap">
                <table className="traveltek-booking-fields-table">
                  <thead>
                    <tr>
                      <th>What needs checking</th>
                      <th>Field</th>
                      <th>Current system value</th>
                      <th>Traveltek value</th>
                      <th>Status</th>
                      <th>Detected</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.updates.map((update) => {
                      const suggestionType = traveltekSuggestionType(update);
                      return (
                        <tr key={update.id}>
                          <td>
                            <span className={`status-pill status-${suggestionType}`}>
                              {traveltekSuggestionTypeLabel(suggestionType)}
                            </span>
                          </td>
                          <td>{update.field_label}</td>
                          <td>{update.current_value || "-"}</td>
                          <td>{update.traveltek_value || "-"}</td>
                          <td>
                            <span className={`status-pill status-${update.status}`}>
                              {update.status === "resolved" ? "Applied" : formatStatusLabel(update.status)}
                            </span>
                          </td>
                          <td>{formatDateTime(update.detected_at)}</td>
                          <td>
                            <div className="table-actions">
                              {update.status !== "reviewing" ? (
                                <button
                                  disabled={updatingId === update.id || updatingGroupRef === group.booking_ref}
                                  onClick={() => handleStatusChange(update.id, "reviewing")}
                                  type="button"
                                >
                                  Review
                                </button>
                              ) : null}
                              {update.status !== "resolved" ? (
                                <button
                                  disabled={updatingId === update.id || updatingGroupRef === group.booking_ref}
                                  onClick={() => handleStatusChange(update.id, "resolved")}
                                  type="button"
                                >
                                  Apply
                                </button>
                              ) : null}
                              {update.status !== "ignored" ? (
                                <button
                                  disabled={updatingId === update.id || updatingGroupRef === group.booking_ref}
                                  onClick={() => handleStatusChange(update.id, "ignored")}
                                  type="button"
                                >
                                  Ignore
                                </button>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </div>
      ) : (
        <p className="muted-note">No Traveltek update suggestions match this filter.</p>
      )}
    </section>
  );
}

const adjustmentFields = [
  ["gross_booking_value", "Traveltek total cost", "raw_gross_booking_value"],
  ["customer_sings_total", "SINGs in", "raw_customer_sings_total"],
  ["customer_tt_total", "Traveltek total amount paid", "raw_customer_tt_total"],
  ["expected_supplier_total", "Expected supplier cost", "raw_expected_supplier_total"],
  ["supplier_taps_total", "TAPs paid", "raw_supplier_taps_total"],
  ["supplier_tt_total", "Traveltek paid to supplier", "raw_supplier_tt_total"],
];

function moneyInputValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(Number(value).toFixed(2));
}

function decimalOrNull(value) {
  if (value === "" || value === null || value === undefined) {
    return null;
  }
  return Number(value);
}

function amountMatches(value, rawValue) {
  if (value === "" || value === null || value === undefined) {
    return rawValue === null || rawValue === undefined;
  }
  if (rawValue === null || rawValue === undefined) {
    return false;
  }
  return Number(value).toFixed(2) === Number(rawValue).toFixed(2);
}

function csvValue(value) {
  const text = value === null || value === undefined ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function downloadCsv(filename, headers, rows) {
  const lines = [
    headers.map(csvValue).join(","),
    ...rows.map((row) => row.map(csvValue).join(",")),
  ];
  const blob = new Blob([lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function wait(milliseconds) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function boundedNumber(value, fallback, min, max) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.floor(numberValue)));
}

function groupedCheckStatus(row, area) {
  const checks =
    area === "supplier"
      ? [row.supplier_tt_check]
      : [row.customer_tt_check];
  if (checks.includes("mismatch")) {
    return "mismatch";
  }
  if (checks.every((check) => check === "match")) {
    return "match";
  }
  return "waiting";
}

function supplierBalanceDue(row) {
  if (row.expected_supplier_total === null || row.expected_supplier_total === undefined) {
    return null;
  }
  return Number(row.expected_supplier_total) - Number(row.supplier_taps_total || 0);
}

function BookingChecksPage({ token }) {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [search, setSearch] = useState("");
  const [reviewFilter, setReviewFilter] = useState("all");
  const [companyFilter, setCompanyFilter] = useState("all");
  const [supplierFilter, setSupplierFilter] = useState("all");
  const [customerFilter, setCustomerFilter] = useState("all");
  const [editingRef, setEditingRef] = useState("");
  const [draft, setDraft] = useState({});
  const [isSaving, setIsSaving] = useState(false);
  const bookingChecksTopScrollRef = useRef(null);
  const bookingChecksTableScrollRef = useRef(null);
  const [bookingChecksTableWidth, setBookingChecksTableWidth] = useState(1500);

  function loadBookingChecks() {
    return getBookingChecks(token)
      .then((data) => {
        setRows(data.bookings);
        setSummary(data.summary);
        setError("");
      })
      .catch((loadError) => setError(loadError.message || "Booking checks could not load."));
  }

  useEffect(() => {
    loadBookingChecks();
  }, [token]);

  const filteredRows = rows.filter((row) => {
    const searchValue = search.trim().toLowerCase();
    if (
      searchValue &&
      ![
        row.booking_ref,
        row.customer_last_name,
        row.agent_in_charge,
        row.destination,
        row.travel_elements_raw,
        row.normalised_status,
      ]
        .join(" ")
        .toLowerCase()
        .includes(searchValue)
    ) {
      return false;
    }
    if (reviewFilter !== "all" && row.review_status !== reviewFilter) {
      return false;
    }
    if (companyFilter !== "all" && row.booking_company !== companyFilter) {
      return false;
    }
    if (supplierFilter !== "all" && groupedCheckStatus(row, "supplier") !== supplierFilter) {
      return false;
    }
    if (customerFilter !== "all" && groupedCheckStatus(row, "customer") !== customerFilter) {
      return false;
    }
    return true;
  });
  const editingRow = rows.find((row) => row.booking_ref === editingRef);

  useEffect(() => {
    function updateScrollWidth() {
      if (bookingChecksTableScrollRef.current) {
        setBookingChecksTableWidth(bookingChecksTableScrollRef.current.scrollWidth);
      }
    }

    updateScrollWidth();
    window.addEventListener("resize", updateScrollWidth);
    return () => window.removeEventListener("resize", updateScrollWidth);
  }, [filteredRows.length, rows.length, editingRef]);

  function syncBookingChecksScroll(source) {
    const topScroller = bookingChecksTopScrollRef.current;
    const tableScroller = bookingChecksTableScrollRef.current;
    if (!topScroller || !tableScroller) {
      return;
    }

    if (source === "top" && tableScroller.scrollLeft !== topScroller.scrollLeft) {
      tableScroller.scrollLeft = topScroller.scrollLeft;
    }
    if (source === "table" && topScroller.scrollLeft !== tableScroller.scrollLeft) {
      topScroller.scrollLeft = tableScroller.scrollLeft;
    }
  }

  function startEditing(row) {
    setMessage("");
    setError("");
    setEditingRef(row.booking_ref);
    setDraft({
      gross_booking_value: moneyInputValue(row.gross_booking_value),
      customer_sings_total: moneyInputValue(row.customer_sings_total),
      customer_tt_total: moneyInputValue(row.customer_tt_total),
      expected_supplier_total: moneyInputValue(row.expected_supplier_total),
      supplier_taps_total: moneyInputValue(row.supplier_taps_total),
      supplier_tt_total: moneyInputValue(row.supplier_tt_total),
      note: row.manual_adjustment_note || "",
    });
  }

  function updateDraft(fieldName, value) {
    setDraft((current) => ({ ...current, [fieldName]: value }));
  }

  async function saveAdjustments(row) {
    setIsSaving(true);
    setError("");
    setMessage("");

    const adjustments = { note: draft.note || null };
    for (const [fieldName, , rawFieldName] of adjustmentFields) {
      adjustments[fieldName] = amountMatches(draft[fieldName], row[rawFieldName])
        ? null
        : decimalOrNull(draft[fieldName]);
    }

    try {
      const data = await updateBookingCheckAdjustments({
        token,
        bookingRef: row.booking_ref,
        adjustments,
      });
      setRows(data.bookings);
      setSummary(data.summary);
      setEditingRef("");
      setDraft({});
      setMessage(`Saved manual check values for ${row.booking_ref}.`);
    } catch (saveError) {
      setError(saveError.message || "Manual adjustment could not be saved.");
    } finally {
      setIsSaving(false);
    }
  }

  async function clearAdjustments(row) {
    setIsSaving(true);
    setError("");
    setMessage("");
    try {
      const data = await updateBookingCheckAdjustments({
        token,
        bookingRef: row.booking_ref,
        adjustments: {
          gross_booking_value: null,
          expected_supplier_total: null,
          supplier_taps_total: null,
          supplier_tt_total: null,
          customer_sings_total: null,
          customer_tt_total: null,
          note: null,
        },
      });
      setRows(data.bookings);
      setSummary(data.summary);
      setEditingRef("");
      setDraft({});
      setMessage(`Cleared manual check values for ${row.booking_ref}.`);
    } catch (clearError) {
      setError(clearError.message || "Manual adjustment could not be cleared.");
    } finally {
      setIsSaving(false);
    }
  }

  function exportBookingChecksCsv() {
    const headers = [
      "Booking Ref",
      "Company",
      "Customer / Lead",
      "Agent",
      "Status",
      "Destination",
      "Booking Elements",
      "Departure Date",
      "Return Date",
      "Passenger Count",
      "Last Booking Update",
      "Traveltek Total Cost",
      "Traveltek Total Amount Paid",
      "Customer Outstanding (Travel Tek)",
      "SINGs In",
      "SINGs vs Traveltek Paid",
      "SINGs vs Traveltek Paid Variance",
      "Traveltek Total Due",
      "Traveltek Due To Suppliers",
      "Expected Supplier Cost",
      "TAPs Paid",
      "Traveltek Paid To Supplier",
      "TAPs vs Traveltek Supplier Paid",
      "TAPs vs Traveltek Supplier Paid Variance",
      "Expected Supplier Balance",
      "Traveltek Projected Profit",
      "Review Status",
      "Review Note",
      "Manual Adjustment",
      "Manual Adjustment Note",
    ];
    const csvRows = filteredRows.map((row) => [
      row.booking_ref,
      formatSourceLabel(row.booking_company),
      row.customer_last_name || "",
      row.agent_in_charge || "",
      row.normalised_status || "",
      row.destination || "",
      row.travel_elements_raw || "",
      row.departure_date || "",
      row.return_date || "",
      row.passenger_count ?? "",
      formatDateTime(row.updated_at),
      row.gross_booking_value ?? "",
      row.customer_tt_total ?? "",
      row.traveltek_customer_outstanding ?? "",
      row.customer_sings_total ?? "",
      checkLabel(row.customer_tt_check),
      row.customer_tt_variance ?? "",
      row.traveltek_total_due ?? "",
      row.traveltek_due_to_suppliers ?? "",
      row.expected_supplier_total ?? "",
      row.supplier_taps_total ?? "",
      row.supplier_tt_total ?? "",
      checkLabel(row.supplier_tt_check),
      row.supplier_tt_variance ?? "",
      supplierBalanceDue(row) ?? "",
      row.traveltek_projected_profit ?? "",
      checkLabel(row.review_status),
      row.review_note || "",
      row.has_manual_adjustment ? "Yes" : "No",
      row.manual_adjustment_note || "",
    ]);
    downloadCsv("booking-checks.csv", headers, csvRows);
  }

  return (
    <section className="panel booking-checks-panel">
      <div className="panel-heading">
        <div>
          <h2>Booking Checks</h2>
          <p>Booking values compared with actual payments and Traveltek cross-check figures.</p>
        </div>
        <CircleAlert size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="form-success">{message}</p> : null}

      <div className="summary-strip booking-checks-summary">
        <div>
          <span>Bookings</span>
          <strong>{summary?.total_bookings ?? 0}</strong>
        </div>
        <div>
          <span>Full match</span>
          <strong>{summary?.fully_matched ?? 0}</strong>
        </div>
        <div>
          <span>Errors</span>
          <strong>{summary?.error_count ?? 0}</strong>
        </div>
        <div>
          <span>Awaiting imports</span>
          <strong>{summary?.awaiting_count ?? 0}</strong>
        </div>
        <div>
          <span>Supplier payments matched</span>
          <strong>{summary?.supplier_tt_matches ?? 0}</strong>
        </div>
        <div>
          <span>Needs review</span>
          <strong>{summary?.needs_review ?? 0}</strong>
        </div>
      </div>

      <p className="muted-note">
          Traveltek provides the booking framework. TAPs and SINGs are treated as actual payment sources. Supplier payment matching compares TAPs Paid against Traveltek Paid To Supplier.
      </p>

      <div className="booking-check-filters">
        <label>
          Search
          <input
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Booking ref, customer, agent, destination or status"
            type="search"
            value={search}
          />
        </label>
        <label>
          Review
          <select value={reviewFilter} onChange={(event) => setReviewFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="match">Full match</option>
            <option value="mismatch">Errors only</option>
            <option value="waiting">Awaiting imports</option>
          </select>
        </label>
        <label>
          Company
          <select value={companyFilter} onChange={(event) => setCompanyFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="otc">OTC</option>
            <option value="lemieux">LeMieux</option>
            <option value="review">Review</option>
          </select>
        </label>
        <label>
          Supplier checks
          <select value={supplierFilter} onChange={(event) => setSupplierFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="match">Matched</option>
            <option value="mismatch">Errors</option>
            <option value="waiting">Awaiting</option>
          </select>
        </label>
        <label>
          Customer checks
          <select value={customerFilter} onChange={(event) => setCustomerFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="match">Matched</option>
            <option value="mismatch">Errors</option>
            <option value="waiting">Awaiting</option>
          </select>
        </label>
      </div>

      <div className="booking-check-actions">
        <p className="muted-note">Showing {filteredRows.length} of {rows.length} booking check row(s).</p>
        <button className="secondary-button" disabled={!filteredRows.length} onClick={exportBookingChecksCsv} type="button">
          <FileSpreadsheet size={18} aria-hidden="true" />
          Download CSV
        </button>
      </div>

      {editingRow ? (
        <section className="inline-editor">
          <div>
            <div className="section-heading">
              <h3>Amend check values for {editingRow.booking_ref}</h3>
              <p>These values only affect the Booking Checks page. Original imports stay unchanged.</p>
            </div>
            <div className="adjustment-grid">
              {adjustmentFields.map(([fieldName, label, rawFieldName]) => (
                <label key={fieldName}>
                  {label}
                  <input
                    onChange={(event) => updateDraft(fieldName, event.target.value)}
                    step="0.01"
                    type="number"
                    value={draft[fieldName] ?? ""}
                  />
                  <span>Original: {formatMoney(editingRow[rawFieldName])}</span>
                </label>
              ))}
              <label className="adjustment-note">
                Note
                <input
                  onChange={(event) => updateDraft("note", event.target.value)}
                  placeholder="Why this value was amended"
                  value={draft.note || ""}
                />
              </label>
            </div>
            <div className="editor-actions">
              <button className="primary-button" disabled={isSaving} onClick={() => saveAdjustments(editingRow)} type="button">
                Save check values
              </button>
              <button className="secondary-button" disabled={isSaving} onClick={() => clearAdjustments(editingRow)} type="button">
                Clear manual values
              </button>
              <button className="secondary-button" disabled={isSaving} onClick={() => setEditingRef("")} type="button">
                Cancel
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <div
        aria-label="Scroll Booking Checks table left and right"
        className="table-top-scroll"
        onScroll={() => syncBookingChecksScroll("top")}
        ref={bookingChecksTopScrollRef}
      >
        <div className="table-top-scroll-spacer" style={{ width: bookingChecksTableWidth }} />
      </div>

      <div className="table-wrap" onScroll={() => syncBookingChecksScroll("table")} ref={bookingChecksTableScrollRef}>
        <table className="booking-checks-table">
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Customer / Lead</th>
              <th>Agent</th>
              <th>Status</th>
              <th>Destination</th>
              <th>Elements</th>
              <th>Depart</th>
              <th>Return</th>
              <th>Passenger Count</th>
              <th>Last Booking Update</th>
              <th>Traveltek Total Cost</th>
              <th>Traveltek Total Amount Paid</th>
              <th>Customer Outstanding (Travel Tek)</th>
              <th>SINGs In</th>
              <th>SINGs vs Traveltek Paid</th>
              <th>Traveltek Total Due</th>
              <th>Traveltek Due To Suppliers</th>
              <th>Expected Supplier Cost</th>
              <th>TAPs Paid</th>
              <th>Traveltek Paid To Supplier</th>
                <th>TAPs vs Traveltek Paid</th>
                <th>Expected Supplier Balance</th>
                <th>Traveltek Profit</th>
                <th>Review</th>
                <th>Amend</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.length ? (
              filteredRows.map((row) => (
                <tr key={row.booking_ref}>
                  <td>
                    {row.booking_ref}
                    {row.has_manual_adjustment ? (
                      <span className="variance-note">Manual check value</span>
                    ) : null}
                  </td>
                  <td>{row.customer_last_name || "-"}</td>
                  <td>{row.agent_in_charge || "-"}</td>
                  <td>{row.normalised_status || "-"}</td>
                  <td>{row.destination || "-"}</td>
                  <td>{row.travel_elements_raw || "-"}</td>
                  <td>{formatDate(row.departure_date)}</td>
                  <td>{formatDate(row.return_date)}</td>
                  <td>{row.passenger_count ?? "-"}</td>
                  <td>{formatDateTime(row.updated_at)}</td>
                  <td>{formatMoney(row.gross_booking_value)}</td>
                  <td>{formatMoney(row.customer_tt_total)}</td>
                  <td>{formatMoney(row.traveltek_customer_outstanding)}</td>
                  <td>{formatMoney(row.customer_sings_total)}</td>
                  <td>
                    <CheckBadge status={row.customer_tt_check} />
                    <span className="variance-note">{formatMoney(row.customer_tt_variance)}</span>
                  </td>
                  <td>{formatMoney(row.traveltek_total_due)}</td>
                  <td>{formatMoney(row.traveltek_due_to_suppliers)}</td>
                  <td>{formatMoney(row.expected_supplier_total)}</td>
                  <td>{formatMoney(row.supplier_taps_total)}</td>
                  <td>{formatMoney(row.supplier_tt_total)}</td>
                    <td>
                      <CheckBadge status={row.supplier_tt_check} />
                      <span className="variance-note">{formatMoney(row.supplier_tt_variance)}</span>
                    </td>
                    <td>{formatMoney(supplierBalanceDue(row))}</td>
                    <td>{formatMoney(row.traveltek_projected_profit)}</td>
                    <td>
                    <CheckBadge status={row.review_status} />
                    <span className="variance-note">{row.review_note}</span>
                    {row.manual_adjustment_note ? (
                      <span className="variance-note">{row.manual_adjustment_note}</span>
                    ) : null}
                  </td>
                  <td>
                    <button className="table-action-button" onClick={() => startEditing(row)} type="button">
                      Amend
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                  <td colSpan="25">No booking checks match the current filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SupplierPaymentsPage({ token, source = "all" }) {
  const [payments, setPayments] = useState([]);
  const [reconciliations, setReconciliations] = useState([]);
  const [unallocatedTapsPayments, setUnallocatedTapsPayments] = useState([]);
  const [unallocatedTapsTotal, setUnallocatedTapsTotal] = useState(0);
  const [total, setTotal] = useState(0);
  const [filteredTotal, setFilteredTotal] = useState(0);
  const [searchText, setSearchText] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [matchFilter, setMatchFilter] = useState("all");
  const [allocationRefs, setAllocationRefs] = useState({});
  const [allocationMessage, setAllocationMessage] = useState("");
  const [allocatingPaymentId, setAllocatingPaymentId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  function loadSupplierPayments() {
    setIsLoading(true);
    setError("");
    return getSupplierPayments(token, activeSearch, source, matchFilter)
      .then((data) => {
        setPayments(data.payments);
        setReconciliations(data.reconciliations);
        setUnallocatedTapsPayments(data.unallocated_taps_payments || []);
        setUnallocatedTapsTotal(data.unallocated_taps_total || 0);
        setTotal(data.total);
        setFilteredTotal(data.filtered_total);
      })
      .catch((loadError) => setError(loadError.message || "Supplier payments could not load."))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    loadSupplierPayments();
  }, [token, activeSearch, source, matchFilter]);

  function handleSearchSubmit(event) {
    event.preventDefault();
    setActiveSearch(searchText.trim());
  }

  function clearSearch() {
    setSearchText("");
    setActiveSearch("");
  }

  function setAllocationRef(paymentId, value) {
    setAllocationRefs((current) => ({ ...current, [paymentId]: value }));
  }

  async function handleAllocatePayment(payment) {
    const bookingRef = ((allocationRefs[payment.id] ?? payment.booking_ref) || "").trim();
    if (!bookingRef) {
      setError("Enter the booking reference to attach this supplier payment.");
      return;
    }

    setAllocatingPaymentId(payment.id);
    setError("");
    setAllocationMessage("");
    try {
      const updatedPayment = await allocateSupplierPayment(token, payment.id, bookingRef);
      setAllocationRefs((current) => ({ ...current, [payment.id]: "" }));
      setAllocationMessage(`Supplier payment ${payment.id} is now attached to ${updatedPayment.booking_ref}.`);
      await loadSupplierPayments();
    } catch (allocationError) {
      setError(allocationError.message || "Could not attach this supplier payment.");
    } finally {
      setAllocatingPaymentId(null);
    }
  }

  return (
    <section className="panel supplier-panel">
      <div className="panel-heading">
        <div>
          <h2>{source === "tt" ? "Supplier Payments TT" : "Supplier Payments TAPs"}</h2>
          <p>
            {total} imported {source === "tt" ? "TT human input" : "TAPs actual"} supplier payment rows
          </p>
        </div>
        <ReceiptText size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {allocationMessage ? <p className="form-success">{allocationMessage}</p> : null}

      <form className="supplier-search" onSubmit={handleSearchSubmit}>
        <label>
          Search supplier payments
          <input
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="Booking ref, supplier, product or payment method"
            type="search"
            value={searchText}
          />
        </label>
        <label>
          Match status
          <select onChange={(event) => setMatchFilter(event.target.value)} value={matchFilter}>
            <option value="all">All rows</option>
            <option value="unmatched">Unmatched only</option>
            <option value="matched">Matched only</option>
          </select>
        </label>
        <button className="primary-button" disabled={isLoading} type="submit">
          <Search size={18} aria-hidden="true" />
          Search
        </button>
        <button className="secondary-button" disabled={isLoading && !activeSearch} onClick={clearSearch} type="button">
          <RefreshCw size={18} aria-hidden="true" />
          Clear
        </button>
      </form>

      <p className="muted-note">
        {activeSearch
          ? `Showing ${filteredTotal} matching supplier payment row(s) out of ${total}.`
          : matchFilter !== "all"
            ? `Showing ${filteredTotal} ${matchFilter} supplier payment row(s) out of ${total}.`
          : source === "tt"
            ? "Showing TT human-input supplier rows for cross-checking against TAPs."
            : "Showing TAPs actual supplier payment rows. TT values appear in the reconciliation table for cross-checking."}
      </p>

      {source === "taps" ? (
        <>
          <div className="section-heading">
            <h3>Unallocated TAPs payments</h3>
            <p>TAPs payment rows that have not been matched to a booking yet.</p>
          </div>
          <p className="muted-note">
            Showing {unallocatedTapsPayments.length} of {unallocatedTapsTotal} unallocated TAPs payment row(s).
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Current Ref</th>
                  <th>Product</th>
                  <th>Supplier</th>
                  <th>Payment Supplier</th>
                  <th>Method</th>
                  <th>Payment Value</th>
                  <th>Attach to Booking</th>
                </tr>
              </thead>
              <tbody>
                {unallocatedTapsPayments.length ? (
                  unallocatedTapsPayments.map((payment) => (
                    <tr key={payment.id}>
                      <td>{formatDate(payment.supplier_payment_date)}</td>
                      <td>{payment.booking_ref || "-"}</td>
                      <td>{payment.product_type || "-"}</td>
                      <td>{payment.supplier_name || "-"}</td>
                      <td>{payment.payment_supplier_name || "-"}</td>
                      <td>{payment.supplier_payment_method || "-"}</td>
                      <td>{formatMoney(payment.supplier_payment_amount)}</td>
                      <td>
                        <div className="inline-action">
                          <input
                            aria-label={`Booking reference for TAPs payment ${payment.id}`}
                            onChange={(event) => setAllocationRef(payment.id, event.target.value)}
                            placeholder="OTC-01436"
                            type="text"
                            value={allocationRefs[payment.id] ?? payment.booking_ref ?? ""}
                          />
                          <button
                            className="secondary-button"
                            disabled={allocatingPaymentId === payment.id}
                            onClick={() => handleAllocatePayment(payment)}
                            type="button"
                          >
                            Attach
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="8">No unallocated TAPs payments found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      <div className="section-heading">
        <h3>Booking reconciliation</h3>
        <p>Expected supplier nett plus insurance costs, minus separately imported supplier payments.</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Last Name</th>
              <th>Expected Nett</th>
              <th>Insurance</th>
              <th>Total Cost</th>
              <th>TAPs Paid</th>
              <th>TT Input</th>
              <th>TAPs vs TT</th>
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
                  <td>{formatMoney(item.insurance_cost_total)}</td>
                  <td>{formatMoney(item.total_expected_booking_cost)}</td>
                  <td>{formatMoney(item.supplier_payments_taps_total)}</td>
                  <td>{formatMoney(item.supplier_payments_tt_total)}</td>
                  <td>{formatMoney(item.supplier_cross_check_variance)}</td>
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
                <td colSpan="14">
                  {activeSearch
                    ? "No booking reconciliation rows match this search."
                    : "No bookings are ready for supplier reconciliation yet."}
                </td>
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
              <th>Source</th>
              <th>Booking Ref</th>
              <th>Product</th>
              <th>Supplier</th>
              <th>Payment Supplier</th>
              <th>Method</th>
              <th>Payment Value</th>
              <th>VAT</th>
              <th>Match</th>
              <th>Duplicate</th>
              <th>Attach</th>
            </tr>
          </thead>
          <tbody>
            {payments.length ? (
              payments.map((payment) => (
                <tr key={payment.id}>
                  <td>{formatDate(payment.supplier_payment_date)}</td>
                  <td>{formatSourceLabel(payment.payment_source)}</td>
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
                  <td>
                    {payment.match_status === "matched" ? (
                      payment.booking_ref || "-"
                    ) : (
                      <div className="inline-action">
                        <input
                          aria-label={`Booking reference for supplier payment ${payment.id}`}
                          onChange={(event) => setAllocationRef(payment.id, event.target.value)}
                          placeholder="OTC-01436"
                          type="text"
                          value={allocationRefs[payment.id] ?? payment.booking_ref ?? ""}
                        />
                        <button
                          className="secondary-button"
                          disabled={allocatingPaymentId === payment.id}
                          onClick={() => handleAllocatePayment(payment)}
                          type="button"
                        >
                          Attach
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="12">
                  {activeSearch ? "No supplier payment rows match this search." : "No supplier payment rows imported yet."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CustomerPaymentsPage({ token }) {
  const [payments, setPayments] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [paymentSortOrder, setPaymentSortOrder] = useState("payment_date_desc");
  const [syncStartDate, setSyncStartDate] = useState(defaultSyncStartDate());
  const [syncEndDate, setSyncEndDate] = useState(toDateInputValue(new Date()));
  const [syncMessage, setSyncMessage] = useState("");
  const [syncWarnings, setSyncWarnings] = useState([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isBackfilling, setIsBackfilling] = useState(false);

  function loadCustomerPayments() {
    return getCustomerPayments(token)
      .then((data) => {
        setPayments(data.payments);
        setSummary(data.summary);
      })
      .catch((loadError) => setError(loadError.message || "Customer payments could not load."));
  }

  useEffect(() => {
    loadCustomerPayments();
  }, [token]);

  const sortedPayments = [...payments].sort((left, right) => {
    if (paymentSortOrder === "booking_ref_asc" || paymentSortOrder === "booking_ref_desc") {
      const leftRef = String(left.booking_ref || "").trim();
      const rightRef = String(right.booking_ref || "").trim();
      if (!leftRef && rightRef) {
        return 1;
      }
      if (leftRef && !rightRef) {
        return -1;
      }
      const comparison = leftRef.localeCompare(rightRef, undefined, {
        numeric: true,
        sensitivity: "base",
      });
      return paymentSortOrder === "booking_ref_desc" ? -comparison : comparison;
    }

    const leftDate = left.payment_date || "";
    const rightDate = right.payment_date || "";
    const dateComparison = rightDate.localeCompare(leftDate);
    if (dateComparison !== 0) {
      return dateComparison;
    }
    return String(right.booking_ref || "").localeCompare(String(left.booking_ref || ""), undefined, {
      numeric: true,
      sensitivity: "base",
    });
  });

  async function handleFellohSync(event) {
    event.preventDefault();
    setError("");
    setSyncMessage("");
    setSyncWarnings([]);
    setIsSyncing(true);
    try {
      const result = await syncFellohCustomerPayments({
        token,
        startDate: syncStartDate,
        endDate: syncEndDate,
      });
      setSyncMessage(
        `Felloh sync complete: ${result.created_rows} new, ${result.checked_rows} cross-checked, ${result.updated_rows} updated, ${result.skipped_rows} skipped.`
      );
      setSyncWarnings(result.warnings || []);
      await loadCustomerPayments();
    } catch (syncError) {
      setError(syncError.message || "Felloh sync failed.");
    } finally {
      setIsSyncing(false);
    }
  }

  async function handleFellohBackfill() {
    setError("");
    setSyncMessage("");
    setSyncWarnings([]);
    setIsBackfilling(true);
    try {
      const result = await startFellohCustomerPaymentBackfill({
        token,
        startDate: FELLOH_CATCH_UP_START_DATE,
        endDate: syncEndDate,
        chunkDays: 14,
      });
      setSyncMessage(result.message);
    } catch (backfillError) {
      setError(backfillError.message || "Felloh catch-up sync failed to start.");
    } finally {
      setIsBackfilling(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Customer Payments</h2>
          <p>SINGs/Singhs customer receipt data is the trusted customer payment source.</p>
        </div>
        <CreditCard size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {syncMessage ? <p className="form-success">{syncMessage}</p> : null}
      {syncWarnings.length ? (
        <p className="muted-note">{syncWarnings.join(" ")}</p>
      ) : null}

      <form className="customer-sync" onSubmit={handleFellohSync}>
        <label>
          Felloh from
          <input
            onChange={(event) => setSyncStartDate(event.target.value)}
            required
            type="date"
            value={syncStartDate}
          />
        </label>
        <label>
          Felloh to
          <input
            onChange={(event) => setSyncEndDate(event.target.value)}
            required
            type="date"
            value={syncEndDate}
          />
        </label>
        <button className="primary-button" disabled={isSyncing || isBackfilling} type="submit">
          <RefreshCw size={18} aria-hidden="true" />
          {isSyncing ? "Syncing" : "Sync Felloh"}
        </button>
        <button className="secondary-button" disabled={isSyncing || isBackfilling} onClick={handleFellohBackfill} type="button">
          <RefreshCw size={18} aria-hidden="true" />
          {isBackfilling ? "Starting" : "Start 2023 Catch-up"}
        </button>
      </form>

      <div className="summary-strip">
        <div>
          <span>Rows</span>
          <strong>{summary?.total_rows ?? 0}</strong>
        </div>
        <div>
          <span>Total gross rows</span>
          <strong>{formatMoney(summary?.gross_total)}</strong>
        </div>
        <div>
          <span>SINGs actual</span>
          <strong>{formatMoney(summary?.sings_gross_total)}</strong>
        </div>
        <div>
          <span>TT human input</span>
          <strong>{formatMoney(summary?.tt_gross_total)}</strong>
        </div>
        <div>
          <span>SINGs vs TT</span>
          <strong>{formatMoney(summary?.source_variance)}</strong>
        </div>
        <div>
          <span>Total fees</span>
          <strong>{formatMoney(summary?.fee_total)}</strong>
        </div>
        <div>
          <span>Net settled</span>
          <strong>{formatMoney(summary?.net_settled_total)}</strong>
        </div>
        <div>
          <span>Estimated fees</span>
          <strong>{formatMoney(summary?.estimated_fee_total)}</strong>
        </div>
        <div>
          <span>Unmatched</span>
          <strong>{summary?.unmatched_count ?? 0}</strong>
        </div>
      </div>

      <div className="booking-page-actions">
        <label>
          Row order
          <select value={paymentSortOrder} onChange={(event) => setPaymentSortOrder(event.target.value)}>
            <option value="payment_date_desc">Payment date, newest first</option>
            <option value="booking_ref_asc">Booking ref, lowest to highest</option>
            <option value="booking_ref_desc">Booking ref, highest to lowest</option>
          </select>
        </label>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Payment Date</th>
              <th>Source</th>
              <th>Settlement</th>
              <th>Booking Ref</th>
              <th>Invoice Ref</th>
              <th>Customer</th>
              <th>Gross</th>
              <th>Fee</th>
              <th>Net Settled</th>
              <th>Method</th>
              <th>Card</th>
              <th>Status</th>
              <th>Fee Source</th>
              <th>Match</th>
            </tr>
          </thead>
          <tbody>
            {sortedPayments.length ? (
              sortedPayments.map((payment) => (
                <tr key={payment.id}>
                  <td>{formatDate(payment.payment_date)}</td>
                  <td>{formatSourceLabel(payment.payment_source)}</td>
                  <td>{formatDate(payment.settlement_date)}</td>
                  <td>{payment.booking_ref || "-"}</td>
                  <td>{payment.invoice_reference || "-"}</td>
                  <td>{payment.customer_name || "-"}</td>
                  <td>{formatMoney(payment.gross_amount)}</td>
                  <td>{formatMoney(payment.fee_amount)}</td>
                  <td>{formatMoney(payment.net_settled_amount)}</td>
                  <td>{payment.payment_method || "-"}</td>
                  <td>{[payment.card_type, payment.card_brand].filter(Boolean).join(" / ") || "-"}</td>
                  <td>{payment.transaction_status || "-"}</td>
                  <td>
                    <span className={`status-pill ${payment.fee_is_estimated ? "status-estimated" : "status-actual"}`}>
                      {payment.fee_is_estimated ? "estimated" : "actual"}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill status-${payment.match_confidence}`}>
                      {formatStatusLabel(payment.match_confidence)}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="14">No customer payment rows imported yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function InsuranceCostsPage({ token }) {
  const [costs, setCosts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getInsuranceCosts(token)
      .then((data) => {
        setCosts(data.costs);
        setSummary(data.summary);
      })
      .catch((loadError) => setError(loadError.message || "Insurance costs could not load."));
  }, [token]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Insurance Costs</h2>
          <p>Insurance rows are stored separately and added to booking cost reconciliation.</p>
        </div>
        <HandCoins size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="summary-strip">
        <div>
          <span>Rows</span>
          <strong>{summary?.total_rows ?? 0}</strong>
        </div>
        <div>
          <span>Active booking rows</span>
          <strong>{summary?.active_rows ?? 0}</strong>
        </div>
        <div>
          <span>Active insurance cost</span>
          <strong>{formatMoney(summary?.active_cost_total)}</strong>
        </div>
        <div>
          <span>Unmatched</span>
          <strong>{summary?.unmatched_count ?? 0}</strong>
        </div>
        <div>
          <span>Duplicates</span>
          <strong>{summary?.duplicate_count ?? 0}</strong>
        </div>
        <div>
          <span>Reconciliation</span>
          <strong>Included</strong>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Lead Name</th>
              <th>Departure</th>
              <th>Supplement</th>
              <th>Gross</th>
              <th>Discount</th>
              <th>Net</th>
              <th>Insurance Cost</th>
              <th>Status</th>
              <th>Match</th>
              <th>Duplicate</th>
            </tr>
          </thead>
          <tbody>
            {costs.length ? (
              costs.map((cost) => (
                <tr key={cost.id}>
                  <td>{cost.booking_ref || "-"}</td>
                  <td>{cost.lead_name || "-"}</td>
                  <td>{formatDate(cost.departure_date)}</td>
                  <td>{cost.supplement_type || "-"}</td>
                  <td>{formatMoney(cost.gross_amount)}</td>
                  <td>{formatMoney(cost.discount_amount)}</td>
                  <td>{formatMoney(cost.net_amount)}</td>
                  <td>{formatMoney(cost.insurance_cost_amount)}</td>
                  <td>
                    <span className={`status-pill status-${cost.insurance_status || "unknown"}`}>
                      {formatStatusLabel(cost.insurance_status)}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill status-${cost.match_status}`}>
                      {formatStatusLabel(cost.match_status)}
                    </span>
                  </td>
                  <td>{cost.is_duplicate ? "Yes" : "No"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="11">No insurance costs imported yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const bankAllocationOptions = [
  { value: "customer_receipt", label: "Customer payment in" },
  { value: "supplier_payment", label: "Supplier payment out" },
  { value: "head_office_cost", label: "Head Office cost" },
  { value: "refund", label: "Refund" },
  { value: "bank_charge", label: "Bank charge" },
  { value: "transfer", label: "Transfer" },
  { value: "sings_settlement", label: "SINGs settlement" },
  { value: "amex_settlement", label: "AMEX settlement" },
  { value: "other", label: "Other" },
];

const emptyBankUnmatchedFilters = {
  date: "",
  description: "",
  moneyIn: "",
  moneyOut: "",
  currentRef: "",
  suggestedType: "all",
};

const emptyBankTransactionFilters = {
  date: "",
  description: "",
  moneyIn: "",
  moneyOut: "",
  balance: "",
  account: "",
  reference: "",
  bookingRef: "",
  type: "all",
  match: "all",
};

const emptyHeadOfficeCostFilters = {
  date: "",
  description: "",
  moneyIn: "",
  moneyOut: "",
  account: "",
  reference: "",
  match: "all",
};

function bankMatchGroup(transaction) {
  if (transaction.match_status === "duplicate") {
    return "duplicate";
  }
  if (transaction.match_status === "accounted_for_elsewhere") {
    return "accounted_for_elsewhere";
  }
  if (
    transaction.match_status === "matched_manual" ||
    transaction.match_status === "matched_booking_ref" ||
    transaction.booking_ref
  ) {
    return "matched";
  }
  return "unmatched";
}

function BankTransactionsPage({ token }) {
  const [transactions, setTransactions] = useState([]);
  const [unallocatedTransactions, setUnallocatedTransactions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [allocationRefs, setAllocationRefs] = useState({});
  const [allocationTypes, setAllocationTypes] = useState({});
  const [allocatingTransactionId, setAllocatingTransactionId] = useState(null);
  const [unmatchedFilters, setUnmatchedFilters] = useState(emptyBankUnmatchedFilters);
  const [transactionFilters, setTransactionFilters] = useState(emptyBankTransactionFilters);
  const nowForTrustBalance = new Date();
  const [manualTrustValue, setManualTrustValue] = useState("");
  const [manualTrustDate, setManualTrustDate] = useState(toDateInputValue(nowForTrustBalance));
  const [manualTrustTime, setManualTrustTime] = useState(toTimeInputValue(nowForTrustBalance));
  const [manualTrustNote, setManualTrustNote] = useState("");
  const [isSavingTrustBalance, setIsSavingTrustBalance] = useState(false);

  function loadBankTransactions() {
    return getBankTransactions(token)
      .then((data) => {
        setTransactions(data.transactions);
        setUnallocatedTransactions(data.unallocated_transactions || []);
        setSummary(data.summary);
        setError("");
      })
      .catch((loadError) => setError(loadError.message || "Bank transactions could not load."));
  }

  useEffect(() => {
    loadBankTransactions();
  }, [token]);

  function setAllocationRef(transactionId, value) {
    setAllocationRefs((current) => ({ ...current, [transactionId]: value }));
  }

  function setAllocationType(transactionId, value) {
    setAllocationTypes((current) => ({ ...current, [transactionId]: value }));
  }

  function setUnmatchedFilter(fieldName, value) {
    setUnmatchedFilters((current) => ({ ...current, [fieldName]: value }));
  }

  function setTransactionFilter(fieldName, value) {
    setTransactionFilters((current) => ({ ...current, [fieldName]: value }));
  }

  function defaultBankAllocationType(transaction) {
    if (transaction.money_out && Number(transaction.money_out) > 0) {
      return "supplier_payment";
    }
    if (transaction.money_in && Number(transaction.money_in) > 0) {
      return "customer_receipt";
    }
    return "other";
  }

  const filteredUnallocatedTransactions = unallocatedTransactions.filter((transaction) => {
    if (!dateMatches(transaction.transaction_date, unmatchedFilters.date)) {
      return false;
    }
    if (!textMatches(transaction.description, unmatchedFilters.description)) {
      return false;
    }
    if (!moneyMatches(transaction.money_in, unmatchedFilters.moneyIn)) {
      return false;
    }
    if (!moneyMatches(transaction.money_out, unmatchedFilters.moneyOut)) {
      return false;
    }
    if (!textMatches(transaction.booking_ref, unmatchedFilters.currentRef)) {
      return false;
    }
    if (
      unmatchedFilters.suggestedType !== "all" &&
      defaultBankAllocationType(transaction) !== unmatchedFilters.suggestedType
    ) {
      return false;
    }
    return true;
  });

  const filteredTransactions = transactions.filter((transaction) => {
    if (!dateMatches(transaction.transaction_date, transactionFilters.date)) {
      return false;
    }
    if (!textMatches(transaction.description, transactionFilters.description)) {
      return false;
    }
    if (!moneyMatches(transaction.money_in, transactionFilters.moneyIn)) {
      return false;
    }
    if (!moneyMatches(transaction.money_out, transactionFilters.moneyOut)) {
      return false;
    }
    if (!moneyMatches(transaction.balance, transactionFilters.balance)) {
      return false;
    }
    if (!textMatches(transaction.account_type, transactionFilters.account)) {
      return false;
    }
    if (!textMatches(transaction.transaction_reference, transactionFilters.reference)) {
      return false;
    }
    if (!textMatches(transaction.booking_ref, transactionFilters.bookingRef)) {
      return false;
    }
    if (transactionFilters.type !== "all" && transaction.allocation_type !== transactionFilters.type) {
      return false;
    }
    if (transactionFilters.match !== "all" && bankMatchGroup(transaction) !== transactionFilters.match) {
      return false;
    }
    return true;
  });

  async function handleAllocateTransaction(transaction) {
    const allocationType = allocationTypes[transaction.id] || defaultBankAllocationType(transaction);
    const bookingRef = allocationType === "head_office_cost" ? "" : (allocationRefs[transaction.id] || transaction.booking_ref || "").trim();
    if (allocationType !== "head_office_cost" && !bookingRef) {
      setError("Enter the booking reference to attach this bank transaction.");
      return;
    }

    setAllocatingTransactionId(transaction.id);
    setError("");
    setMessage("");
    try {
      const updatedTransaction = await allocateBankTransaction({
        token,
        transactionId: transaction.id,
        bookingRef,
        allocationType,
      });
      setAllocationRefs((current) => ({ ...current, [transaction.id]: "" }));
      setMessage(
        allocationType === "head_office_cost"
          ? `Bank transaction ${transaction.id} is now marked as a Head Office cost.`
          : `Bank transaction ${transaction.id} is now attached to ${updatedTransaction.booking_ref}.`
      );
      await loadBankTransactions();
    } catch (allocationError) {
      setError(allocationError.message || "Could not attach this bank transaction.");
    } finally {
      setAllocatingTransactionId(null);
    }
  }

  async function handleManualTrustBalanceSubmit(event) {
    event.preventDefault();
    if (!manualTrustValue || !manualTrustDate || !manualTrustTime) {
      setError("Enter the trust value, date and time checked.");
      return;
    }

    const checkedAt = new Date(`${manualTrustDate}T${manualTrustTime}:00`);
    setIsSavingTrustBalance(true);
    setError("");
    setMessage("");
    try {
      const savedBalance = await createManualTrustBalance({
        token,
        trustValue: Number(manualTrustValue),
        balanceDate: manualTrustDate,
        checkedAt: checkedAt.toISOString(),
        note: manualTrustNote,
      });
      setMessage(`Manual trust balance saved: ${formatMoney(savedBalance.trust_value)}.`);
      setManualTrustNote("");
      await loadBankTransactions();
    } catch (saveError) {
      setError(saveError.message || "Could not save the manual trust balance.");
    } finally {
      setIsSavingTrustBalance(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Bank Transactions</h2>
          <p>Imported trust bank statement rows and latest actual balance.</p>
        </div>
        <Banknote size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="form-success">{message}</p> : null}

      <div className="summary-strip">
        <div>
          <span>Rows</span>
          <strong>{summary?.total_rows ?? 0}</strong>
        </div>
        <div>
          <span>Trust value</span>
          <strong>{formatMoney(summary?.latest_trust_balance)}</strong>
        </div>
        <div>
          <span>Trust date stamp</span>
          <strong>{formatDate(summary?.latest_trust_balance_date)}</strong>
        </div>
        <div>
          <span>Trust time stamp</span>
          <strong>{formatDateTime(summary?.latest_trust_balance_checked_at)}</strong>
        </div>
        <div>
          <span>Matched</span>
          <strong>{summary?.matched_count ?? 0}</strong>
        </div>
        <div>
          <span>Unmatched</span>
          <strong>{summary?.unmatched_count ?? 0}</strong>
        </div>
        <div>
          <span>Duplicates</span>
          <strong>{summary?.duplicate_count ?? 0}</strong>
        </div>
        <div>
          <span>Trust variance source</span>
          <strong>{summary?.latest_trust_balance_source === "manual" ? "Manual value" : "Awaiting manual value"}</strong>
        </div>
      </div>

      <div className="section-heading">
        <h3>Manual trust balance</h3>
        <p>Enter the actual trust account value checked by Head Office.</p>
      </div>
      <form className="manual-trust-form" onSubmit={handleManualTrustBalanceSubmit}>
        <label>
          Trust value
          <input
            min="0"
            onChange={(event) => setManualTrustValue(event.target.value)}
            placeholder="0.00"
            step="0.01"
            type="number"
            value={manualTrustValue}
          />
        </label>
        <label>
          Date checked
          <input onChange={(event) => setManualTrustDate(event.target.value)} type="date" value={manualTrustDate} />
        </label>
        <label>
          Time checked
          <input onChange={(event) => setManualTrustTime(event.target.value)} type="time" value={manualTrustTime} />
        </label>
        <label>
          Note
          <input
            onChange={(event) => setManualTrustNote(event.target.value)}
            placeholder="Optional"
            type="text"
            value={manualTrustNote}
          />
        </label>
        <button className="primary-button" disabled={isSavingTrustBalance} type="submit">
          Save trust value
        </button>
      </form>

      <div className="section-heading">
        <h3>Unmatched bank transactions</h3>
        <p>Attach bank rows to a booking when the description did not match automatically.</p>
      </div>
      <div className="field-filter-grid bank-unmatched-filters">
        <label>
          Date
          <input
            onChange={(event) => setUnmatchedFilter("date", event.target.value)}
            placeholder="27 Feb 2026"
            type="search"
            value={unmatchedFilters.date}
          />
        </label>
        <label>
          Description
          <input
            onChange={(event) => setUnmatchedFilter("description", event.target.value)}
            placeholder="Supplier or reference"
            type="search"
            value={unmatchedFilters.description}
          />
        </label>
        <label>
          Money in
          <input
            onChange={(event) => setUnmatchedFilter("moneyIn", event.target.value)}
            placeholder="Amount"
            type="search"
            value={unmatchedFilters.moneyIn}
          />
        </label>
        <label>
          Money out
          <input
            onChange={(event) => setUnmatchedFilter("moneyOut", event.target.value)}
            placeholder="Amount"
            type="search"
            value={unmatchedFilters.moneyOut}
          />
        </label>
        <label>
          Current ref
          <input
            onChange={(event) => setUnmatchedFilter("currentRef", event.target.value)}
            placeholder="OTC-01436"
            type="search"
            value={unmatchedFilters.currentRef}
          />
        </label>
        <label>
          Suggested type
          <select
            onChange={(event) => setUnmatchedFilter("suggestedType", event.target.value)}
            value={unmatchedFilters.suggestedType}
          >
            <option value="all">All</option>
            <option value="customer_receipt">Customer payment in</option>
            <option value="supplier_payment">Supplier payment out</option>
            <option value="other">Other</option>
          </select>
        </label>
        <button className="secondary-button" onClick={() => setUnmatchedFilters(emptyBankUnmatchedFilters)} type="button">
          Clear filters
        </button>
      </div>
      <p className="muted-note">
        Showing {filteredUnallocatedTransactions.length} of {unallocatedTransactions.length} unmatched row(s).
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Money In</th>
              <th>Money Out</th>
              <th>Current Ref</th>
              <th>Attach to Booking</th>
            </tr>
          </thead>
          <tbody>
            {filteredUnallocatedTransactions.length ? (
              filteredUnallocatedTransactions.map((transaction) => {
                const selectedType = allocationTypes[transaction.id] || defaultBankAllocationType(transaction);
                const isHeadOfficeCost = selectedType === "head_office_cost";
                return (
                  <tr key={transaction.id}>
                    <td>{formatDate(transaction.transaction_date)}</td>
                    <td>{transaction.description || "-"}</td>
                    <td>{formatMoney(transaction.money_in)}</td>
                    <td>{formatMoney(transaction.money_out)}</td>
                    <td>{transaction.booking_ref || "-"}</td>
                    <td>
                      <div className="inline-action inline-action-wide">
                        <input
                          aria-label={`Booking reference for bank transaction ${transaction.id}`}
                          disabled={isHeadOfficeCost}
                          onChange={(event) => setAllocationRef(transaction.id, event.target.value)}
                          placeholder={isHeadOfficeCost ? "No booking needed" : "OTC-01436"}
                          type="text"
                          value={isHeadOfficeCost ? "" : allocationRefs[transaction.id] || transaction.booking_ref || ""}
                        />
                        <select
                          aria-label={`Allocation type for bank transaction ${transaction.id}`}
                          onChange={(event) => setAllocationType(transaction.id, event.target.value)}
                          value={selectedType}
                        >
                          {bankAllocationOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                        <button
                          className="secondary-button"
                          disabled={allocatingTransactionId === transaction.id}
                          onClick={() => handleAllocateTransaction(transaction)}
                          type="button"
                        >
                          {isHeadOfficeCost ? "Save" : "Attach"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan="6">No unmatched bank transactions found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="section-heading">
        <h3>Imported bank rows</h3>
        <p>Search each bank statement field and filter by type or match status.</p>
      </div>
      <div className="field-filter-grid bank-transaction-filters">
        <label>
          Date
          <input
            onChange={(event) => setTransactionFilter("date", event.target.value)}
            placeholder="27 Feb 2026"
            type="search"
            value={transactionFilters.date}
          />
        </label>
        <label>
          Description
          <input
            onChange={(event) => setTransactionFilter("description", event.target.value)}
            placeholder="Text"
            type="search"
            value={transactionFilters.description}
          />
        </label>
        <label>
          Money in
          <input
            onChange={(event) => setTransactionFilter("moneyIn", event.target.value)}
            placeholder="Amount"
            type="search"
            value={transactionFilters.moneyIn}
          />
        </label>
        <label>
          Money out
          <input
            onChange={(event) => setTransactionFilter("moneyOut", event.target.value)}
            placeholder="Amount"
            type="search"
            value={transactionFilters.moneyOut}
          />
        </label>
        <label>
          Balance
          <input
            onChange={(event) => setTransactionFilter("balance", event.target.value)}
            placeholder="Amount"
            type="search"
            value={transactionFilters.balance}
          />
        </label>
        <label>
          Account
          <input
            onChange={(event) => setTransactionFilter("account", event.target.value)}
            placeholder="Trust"
            type="search"
            value={transactionFilters.account}
          />
        </label>
        <label>
          Reference
          <input
            onChange={(event) => setTransactionFilter("reference", event.target.value)}
            placeholder="Bank ref"
            type="search"
            value={transactionFilters.reference}
          />
        </label>
        <label>
          Booking ref
          <input
            onChange={(event) => setTransactionFilter("bookingRef", event.target.value)}
            placeholder="OTC-01436"
            type="search"
            value={transactionFilters.bookingRef}
          />
        </label>
        <label>
          Type
          <select onChange={(event) => setTransactionFilter("type", event.target.value)} value={transactionFilters.type}>
            <option value="all">All</option>
            {bankAllocationOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Match
          <select
            onChange={(event) => setTransactionFilter("match", event.target.value)}
            value={transactionFilters.match}
          >
            <option value="all">All</option>
            <option value="matched">Matched</option>
            <option value="unmatched">Unmatched</option>
            <option value="accounted_for_elsewhere">Accounted elsewhere</option>
            <option value="duplicate">Duplicate</option>
          </select>
        </label>
        <button
          className="secondary-button"
          onClick={() => setTransactionFilters(emptyBankTransactionFilters)}
          type="button"
        >
          Clear filters
        </button>
      </div>
      <p className="muted-note">Showing {filteredTransactions.length} of {transactions.length} imported bank row(s).</p>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Money In</th>
              <th>Money Out</th>
              <th>Balance</th>
              <th>Account</th>
              <th>Reference</th>
              <th>Booking Ref</th>
              <th>Type</th>
              <th>Match</th>
            </tr>
          </thead>
          <tbody>
            {filteredTransactions.length ? (
              filteredTransactions.map((transaction) => (
                <tr key={transaction.id}>
                  <td>{formatDate(transaction.transaction_date)}</td>
                  <td>{transaction.description || "-"}</td>
                  <td>{formatMoney(transaction.money_in)}</td>
                  <td>{formatMoney(transaction.money_out)}</td>
                  <td>{formatMoney(transaction.balance)}</td>
                  <td>{transaction.account_type || "-"}</td>
                  <td>{transaction.transaction_reference || "-"}</td>
                  <td>{transaction.booking_ref || "-"}</td>
                  <td>{formatStatusLabel(transaction.allocation_type)}</td>
                  <td>
                    <span className={`status-pill status-${transaction.match_status}`}>
                      {formatStatusLabel(transaction.match_status)}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="10">No bank statement rows match the current filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function HeadOfficeCostsPage({ token }) {
  const [costs, setCosts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [filters, setFilters] = useState(emptyHeadOfficeCostFilters);
  const [error, setError] = useState("");

  useEffect(() => {
    getHeadOfficeCosts(token)
      .then((data) => {
        setCosts(data.costs || []);
        setSummary(data.summary);
        setError("");
      })
      .catch((loadError) => setError(loadError.message || "Head Office costs could not load."));
  }, [token]);

  function setCostFilter(fieldName, value) {
    setFilters((current) => ({ ...current, [fieldName]: value }));
  }

  const filteredCosts = costs.filter((cost) => {
    if (!dateMatches(cost.transaction_date, filters.date)) {
      return false;
    }
    if (!textMatches(cost.description, filters.description)) {
      return false;
    }
    if (!moneyMatches(cost.money_in, filters.moneyIn)) {
      return false;
    }
    if (!moneyMatches(cost.money_out, filters.moneyOut)) {
      return false;
    }
    if (!textMatches(cost.account_type, filters.account)) {
      return false;
    }
    if (!textMatches(cost.transaction_reference, filters.reference)) {
      return false;
    }
    if (filters.match !== "all" && bankMatchGroup(cost) !== filters.match) {
      return false;
    }
    return true;
  });

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Head Office Costs</h2>
          <p>Bank transactions manually marked as Head Office costs.</p>
        </div>
        <Banknote size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="summary-strip summary-strip-wide">
        <div>
          <span>Cost rows</span>
          <strong>{summary?.total_rows ?? 0}</strong>
        </div>
        <div>
          <span>Money out</span>
          <strong>{formatMoney(summary?.total_money_out)}</strong>
        </div>
        <div>
          <span>Money in</span>
          <strong>{formatMoney(summary?.total_money_in)}</strong>
        </div>
        <div>
          <span>Net spend</span>
          <strong>{formatMoney(summary?.net_spend)}</strong>
        </div>
        <div>
          <span>Date range</span>
          <strong>
            {summary?.first_date || summary?.last_date
              ? `${formatDate(summary?.first_date)} to ${formatDate(summary?.last_date)}`
              : "-"}
          </strong>
        </div>
      </div>

      <div className="field-filter-grid bank-transaction-filters">
        <label>
          Date
          <input
            onChange={(event) => setCostFilter("date", event.target.value)}
            placeholder="27 Feb 2026"
            type="search"
            value={filters.date}
          />
        </label>
        <label>
          Description
          <input
            onChange={(event) => setCostFilter("description", event.target.value)}
            placeholder="Text"
            type="search"
            value={filters.description}
          />
        </label>
        <label>
          Money in
          <input
            onChange={(event) => setCostFilter("moneyIn", event.target.value)}
            placeholder="Amount"
            type="search"
            value={filters.moneyIn}
          />
        </label>
        <label>
          Money out
          <input
            onChange={(event) => setCostFilter("moneyOut", event.target.value)}
            placeholder="Amount"
            type="search"
            value={filters.moneyOut}
          />
        </label>
        <label>
          Account
          <input
            onChange={(event) => setCostFilter("account", event.target.value)}
            placeholder="Trust"
            type="search"
            value={filters.account}
          />
        </label>
        <label>
          Reference
          <input
            onChange={(event) => setCostFilter("reference", event.target.value)}
            placeholder="Bank ref"
            type="search"
            value={filters.reference}
          />
        </label>
        <label>
          Match
          <select onChange={(event) => setCostFilter("match", event.target.value)} value={filters.match}>
            <option value="all">All</option>
            <option value="matched">Matched</option>
            <option value="unmatched">Unmatched</option>
          </select>
        </label>
        <button className="secondary-button" onClick={() => setFilters(emptyHeadOfficeCostFilters)} type="button">
          Clear filters
        </button>
      </div>
      <p className="muted-note">Showing {filteredCosts.length} of {costs.length} Head Office cost row(s).</p>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Money In</th>
              <th>Money Out</th>
              <th>Balance</th>
              <th>Account</th>
              <th>Reference</th>
              <th>Match</th>
            </tr>
          </thead>
          <tbody>
            {filteredCosts.length ? (
              filteredCosts.map((cost) => (
                <tr key={cost.id}>
                  <td>{formatDate(cost.transaction_date)}</td>
                  <td>{cost.description || "-"}</td>
                  <td>{formatMoney(cost.money_in)}</td>
                  <td>{formatMoney(cost.money_out)}</td>
                  <td>{formatMoney(cost.balance)}</td>
                  <td>{cost.account_type || "-"}</td>
                  <td>{cost.transaction_reference || "-"}</td>
                  <td>
                    <span className={`status-pill status-${cost.match_status}`}>
                      {formatStatusLabel(cost.match_status)}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="8">No Head Office costs match the current filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RefundsPage({ token }) {
  const [refunds, setRefunds] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getRefunds(token)
      .then((data) => {
        setRefunds(data.refunds);
        setSummary(data.summary);
      })
      .catch((loadError) => setError(loadError.message || "Refunds could not load."));
  }, [token]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Refunds</h2>
          <p>Refund liabilities and supplier refund recovery tracking.</p>
        </div>
        <RefreshCw size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="summary-strip summary-strip-wide">
        <div>
          <span>Rows</span>
          <strong>{summary?.total_rows ?? 0}</strong>
        </div>
        <div>
          <span>Refund due</span>
          <strong>{formatMoney(summary?.refund_amount_due_total)}</strong>
        </div>
        <div>
          <span>Refund paid</span>
          <strong>{formatMoney(summary?.refund_amount_paid_total)}</strong>
        </div>
        <div>
          <span>Unpaid refunds</span>
          <strong>{formatMoney(summary?.refund_unpaid_total)}</strong>
        </div>
        <div>
          <span>Supplier expected</span>
          <strong>{formatMoney(summary?.supplier_refund_expected_total)}</strong>
        </div>
        <div>
          <span>Supplier received</span>
          <strong>{formatMoney(summary?.supplier_refund_received_total)}</strong>
        </div>
        <div>
          <span>Supplier outstanding</span>
          <strong>{formatMoney(summary?.supplier_refund_outstanding_total)}</strong>
        </div>
        <div>
          <span>Overdue</span>
          <strong>{summary?.overdue_count ?? 0}</strong>
        </div>
        <div>
          <span>Unmatched</span>
          <strong>{summary?.unmatched_count ?? 0}</strong>
        </div>
        <div>
          <span>Trust impact</span>
          <strong>{summary?.total_rows ? "Included" : "No refunds"}</strong>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Customer</th>
              <th>Reason</th>
              <th>Due</th>
              <th>Paid</th>
              <th>Unpaid</th>
              <th>Status</th>
              <th>Supplier Expected</th>
              <th>Supplier Received</th>
              <th>Supplier Outstanding</th>
              <th>Due Date</th>
              <th>Paid Date</th>
              <th>Match</th>
            </tr>
          </thead>
          <tbody>
            {refunds.length ? (
              refunds.map((refund) => (
                <tr key={refund.id}>
                  <td>{refund.booking_ref || "-"}</td>
                  <td>{refund.customer_name || "-"}</td>
                  <td>{refund.refund_reason || "-"}</td>
                  <td>{formatMoney(refund.refund_amount_due)}</td>
                  <td>{formatMoney(refund.refund_amount_paid)}</td>
                  <td>{formatMoney(refund.refund_unpaid)}</td>
                  <td>
                    <span className={`status-pill status-${refund.refund_status}`}>
                      {formatStatusLabel(refund.refund_status)}
                    </span>
                  </td>
                  <td>{formatMoney(refund.supplier_refund_expected)}</td>
                  <td>{formatMoney(refund.supplier_refund_received)}</td>
                  <td>{formatMoney(refund.supplier_refund_outstanding)}</td>
                  <td>{formatDate(refund.due_date)}</td>
                  <td>{formatDate(refund.paid_date)}</td>
                  <td>
                    <span className={`status-pill status-${refund.match_status}`}>
                      {formatStatusLabel(refund.match_status)}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="13">No refunds imported yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AgentCommissionsPage({ token }) {
  const [commissions, setCommissions] = useState([]);
  const [trueProfits, setTrueProfits] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getAgentCommissions(token)
      .then((data) => {
        setCommissions(data.commissions);
        setTrueProfits(data.true_profits);
        setSummary(data.summary);
      })
      .catch((loadError) => setError(loadError.message || "Agent commissions could not load."));
  }, [token]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Agent Commissions</h2>
          <p>Commission imports and true booking profitability calculated by the system.</p>
        </div>
        <HandCoins size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="summary-strip summary-strip-wide">
        <div>
          <span>Rows</span>
          <strong>{summary?.total_rows ?? 0}</strong>
        </div>
        <div>
          <span>Gross commission</span>
          <strong>{formatMoney(summary?.gross_commission_total)}</strong>
        </div>
        <div>
          <span>Deductions</span>
          <strong>{formatMoney(summary?.deductions_total)}</strong>
        </div>
        <div>
          <span>Net commission due</span>
          <strong>{formatMoney(summary?.net_commission_due_total)}</strong>
        </div>
        <div>
          <span>Accrued</span>
          <strong>{summary?.accrued_count ?? 0}</strong>
        </div>
        <div>
          <span>Due</span>
          <strong>{summary?.due_count ?? 0}</strong>
        </div>
        <div>
          <span>Paid</span>
          <strong>{summary?.paid_count ?? 0}</strong>
        </div>
        <div>
          <span>Withheld</span>
          <strong>{summary?.withheld_count ?? 0}</strong>
        </div>
        <div>
          <span>Clawed back</span>
          <strong>{summary?.clawed_back_count ?? 0}</strong>
        </div>
        <div>
          <span>Unmatched</span>
          <strong>{summary?.unmatched_count ?? 0}</strong>
        </div>
      </div>

      <div className="section-heading">
        <h3>True profitability</h3>
          <p>Gross value minus supplier nett, insurance, payment fees, commission and refunds, cross-checked against Traveltek profit.</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Last Name</th>
              <th>Gross Value</th>
              <th>Supplier Nett</th>
              <th>Insurance</th>
              <th>Payment Fees</th>
              <th>Commission</th>
                <th>Refunds</th>
                <th>True Profit</th>
                <th>TT Profit</th>
                <th>Profit Variance</th>
                <th>Margin</th>
                <th>Status</th>
              <th>Missing Data</th>
            </tr>
          </thead>
          <tbody>
            {trueProfits.length ? (
              trueProfits.map((profit) => (
                <tr key={profit.booking_ref}>
                  <td>{profit.booking_ref}</td>
                  <td>{profit.customer_last_name || "-"}</td>
                  <td>{formatMoney(profit.gross_booking_value)}</td>
                  <td>{formatMoney(profit.expected_supplier_nett)}</td>
                  <td>{formatMoney(profit.insurance_costs)}</td>
                  <td>{formatMoney(profit.payment_fees)}</td>
                  <td>{formatMoney(profit.agent_commission)}</td>
                    <td>{formatMoney(profit.refunds_adjustments)}</td>
                    <td>{formatMoney(profit.true_booking_profit)}</td>
                    <td>{formatMoney(profit.traveltek_projected_profit)}</td>
                    <td>{formatMoney(profit.profit_variance_vs_traveltek)}</td>
                    <td>{profit.true_margin_percentage === null ? "-" : `${profit.true_margin_percentage}%`}</td>
                  <td>
                    <span className={`status-pill status-${profit.true_profit_status}`}>
                      {formatStatusLabel(profit.true_profit_status)}
                    </span>
                  </td>
                  <td>{profit.missing_items.length ? profit.missing_items.join("; ") : "None"}</td>
                </tr>
              ))
            ) : (
              <tr>
                  <td colSpan="14">No bookings are ready for true profit calculation yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="section-heading">
        <h3>Imported commission rows</h3>
        <p>Each commission line is stored separately.</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Agent</th>
              <th>Basis</th>
              <th>Gross</th>
              <th>Deductions</th>
              <th>Net Due</th>
              <th>Status</th>
              <th>Due Date</th>
              <th>Paid Date</th>
              <th>Match</th>
            </tr>
          </thead>
          <tbody>
            {commissions.length ? (
              commissions.map((commission) => (
                <tr key={commission.id}>
                  <td>{commission.booking_ref || "-"}</td>
                  <td>{commission.agent_name || "-"}</td>
                  <td>{commission.commission_basis || "-"}</td>
                  <td>{formatMoney(commission.gross_commission)}</td>
                  <td>{formatMoney(commission.deductions)}</td>
                  <td>{formatMoney(commission.net_commission_due)}</td>
                  <td>
                    <span className={`status-pill status-${commission.commission_status}`}>
                      {formatStatusLabel(commission.commission_status)}
                    </span>
                  </td>
                  <td>{formatDate(commission.due_date)}</td>
                  <td>{formatDate(commission.paid_date)}</td>
                  <td>
                    <span className={`status-pill status-${commission.match_status}`}>
                      {formatStatusLabel(commission.match_status)}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="10">No agent commission rows imported yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TrustReconciliationPage({ token }) {
  const [summary, setSummary] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [generatedAt, setGeneratedAt] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getTrustReconciliation(token)
      .then((data) => {
        setSummary(data.summary);
        setBookings(data.bookings);
        setGeneratedAt(data.generated_at);
      })
      .catch((loadError) => setError(loadError.message || "Trust reconciliation could not load."));
  }, [token]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Trust Reconciliation</h2>
          <p>Calculated from SINGs/Singhs payments, supplier payments and refunds.</p>
        </div>
        <Landmark size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="summary-strip summary-strip-wide">
        <div>
          <span>Customer payments</span>
          <strong>{formatMoney(summary?.customer_payments_received)}</strong>
        </div>
        <div>
          <span>Card fees</span>
          <strong>{formatMoney(summary?.card_fees)}</strong>
        </div>
        <div>
          <span>Net trust receipts</span>
          <strong>{formatMoney(summary?.net_trust_receipts)}</strong>
        </div>
        <div>
          <span>Supplier payments</span>
          <strong>{formatMoney(summary?.supplier_payments_made)}</strong>
        </div>
        <div>
          <span>Refunds paid</span>
          <strong>{formatMoney(summary?.refunds_paid)}</strong>
        </div>
        <div>
          <span>Refunds due</span>
          <strong>{formatMoney(summary?.refunds_due)}</strong>
        </div>
        <div>
          <span>Required trust</span>
          <strong>{formatMoney(summary?.required_trust_balance)}</strong>
        </div>
        <div>
          <span>Actual bank balance</span>
          <strong>{formatMoney(summary?.actual_trust_balance)}</strong>
        </div>
        <div>
          <span>Trust variance</span>
          <strong>{formatMoney(summary?.trust_variance)}</strong>
        </div>
        <div>
          <span>Bank status</span>
          <strong>{summary?.bank_status || "Awaiting bank statement"}</strong>
        </div>
      </div>

      <div className="section-heading">
        <h3>Booking trust position</h3>
        <p>Net trust receipts minus supplier payments and refunds paid.</p>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Last Name</th>
              <th>Status</th>
              <th>Gross Value</th>
              <th>Customer Paid</th>
              <th>Card Fees</th>
              <th>Net Trust Receipts</th>
              <th>Supplier Paid</th>
              <th>Refunds Paid</th>
              <th>Refunds Unpaid</th>
              <th>Current Trust Balance</th>
              <th>Required Contribution</th>
              <th>Trust Status</th>
              <th>Missing Data</th>
            </tr>
          </thead>
          <tbody>
            {bookings.length ? (
              bookings.map((booking) => (
                <tr key={booking.booking_ref}>
                  <td>{booking.booking_ref}</td>
                  <td>{booking.customer_last_name || "-"}</td>
                  <td>{booking.booking_status || "-"}</td>
                  <td>{formatMoney(booking.gross_booking_value)}</td>
                  <td>{formatMoney(booking.customer_payments_received)}</td>
                  <td>{formatMoney(booking.card_fees)}</td>
                  <td>{formatMoney(booking.net_trust_receipts)}</td>
                  <td>{formatMoney(booking.supplier_payments_made)}</td>
                  <td>{formatMoney(booking.refunds_paid)}</td>
                  <td>{formatMoney(booking.refunds_unpaid)}</td>
                  <td>{formatMoney(booking.current_booking_trust_balance)}</td>
                  <td>{formatMoney(booking.required_trust_balance_contribution)}</td>
                  <td>
                    <span className={`status-pill status-${booking.trust_status}`}>
                      {formatStatusLabel(booking.trust_status)}
                    </span>
                  </td>
                  <td>{booking.missing_items.length ? booking.missing_items.join("; ") : "None"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="14">No bookings imported yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="muted-note">
        Last calculated {formatDateTime(generatedAt)}. Master Booking Report received values are not used here.
      </p>
    </section>
  );
}

function ExceptionsPage({ token }) {
  const [exceptions, setExceptions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [generation, setGeneration] = useState(null);
  const [statusFilter, setStatusFilter] = useState("open");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  async function loadExceptions() {
    const data = await getExceptions(token, { status: statusFilter, severity: severityFilter });
    setExceptions(data.exceptions);
    setSummary(data.summary);
    setGeneration(data.generation);
  }

  useEffect(() => {
    setError("");
    loadExceptions().catch((loadError) => setError(loadError.message || "Exceptions could not load."));
  }, [token, statusFilter, severityFilter]);

  async function handleGenerate() {
    setIsGenerating(true);
    setMessage("");
    setError("");
    try {
      const result = await generateExceptions(token);
      setMessage(
        `Scan complete: ${result.generated_count} current issue(s), ${result.created_count} new, ${result.auto_resolved_count} resolved.`
      );
      await loadExceptions();
    } catch (generateError) {
      setError(generateError.message || "Exception scan failed.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleStatusChange(exceptionId, status) {
    setError("");
    setMessage("");
    try {
      await updateExceptionStatus({ token, exceptionId, status });
      setMessage(`Exception marked as ${formatStatusLabel(status)}.`);
      await loadExceptions();
    } catch (statusError) {
      setError(statusError.message || "Exception status could not be updated.");
    }
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Exceptions</h2>
          <p>Automated checks for finance, trust and compliance items that need review.</p>
        </div>
        <AlertTriangle size={24} aria-hidden="true" />
      </div>

      <div className="summary-strip summary-strip-wide">
        <div>
          <span>Open</span>
          <strong>{summary?.open_count ?? 0}</strong>
        </div>
        <div>
          <span>Reviewing</span>
          <strong>{summary?.reviewing_count ?? 0}</strong>
        </div>
        <div>
          <span>Critical</span>
          <strong>{summary?.critical_count ?? 0}</strong>
        </div>
        <div>
          <span>High</span>
          <strong>{summary?.high_count ?? 0}</strong>
        </div>
        <div>
          <span>Medium</span>
          <strong>{summary?.medium_count ?? 0}</strong>
        </div>
        <div>
          <span>Low</span>
          <strong>{summary?.low_count ?? 0}</strong>
        </div>
      </div>

      <div className="exception-toolbar">
        <label>
          Status
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="open">Open</option>
            <option value="reviewing">Reviewing</option>
            <option value="resolved">Resolved</option>
            <option value="ignored">Ignored</option>
            <option value="all">All</option>
          </select>
        </label>
        <label>
          Severity
          <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
        <button className="primary-button" disabled={isGenerating} onClick={handleGenerate} type="button">
          <RefreshCw size={18} aria-hidden="true" />
          {isGenerating ? "Scanning" : "Run scan"}
        </button>
      </div>

      {message ? <p className="form-success">{message}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}
      {generation ? (
        <p className="muted-note">
          Latest scan found {generation.generated_count} current issue(s). New: {generation.created_count}. Updated:{" "}
          {generation.updated_count}. Auto-resolved: {generation.auto_resolved_count}.
        </p>
      ) : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Status</th>
              <th>Type</th>
              <th>Title</th>
              <th>Booking</th>
              <th>Detail</th>
              <th>Detected</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {exceptions.length ? (
              exceptions.map((exception) => (
                <tr key={exception.id}>
                  <td>
                    <span className={`status-pill status-severity-${exception.severity}`}>
                      {formatStatusLabel(exception.severity)}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill status-${exception.status}`}>
                      {formatStatusLabel(exception.status)}
                    </span>
                  </td>
                  <td>{formatStatusLabel(exception.exception_type)}</td>
                  <td>{exception.title}</td>
                  <td>{exception.booking_ref || "-"}</td>
                  <td>{exception.detail || "-"}</td>
                  <td>{formatDateTime(exception.detected_at)}</td>
                  <td>
                    <div className="table-actions">
                      {exception.status !== "reviewing" ? (
                        <button type="button" onClick={() => handleStatusChange(exception.id, "reviewing")}>
                          Review
                        </button>
                      ) : null}
                      {exception.status !== "resolved" ? (
                        <button type="button" onClick={() => handleStatusChange(exception.id, "resolved")}>
                          Resolve
                        </button>
                      ) : null}
                      {exception.status !== "ignored" ? (
                        <button type="button" onClick={() => handleStatusChange(exception.id, "ignored")}>
                          Ignore
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="8">No exceptions match these filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function WeeklyReportsPage({ token }) {
  const [latest, setLatest] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [reportTypes, setReportTypes] = useState([]);
  const [selectedReportType, setSelectedReportType] = useState("");
  const [reportRuns, setReportRuns] = useState([]);
  const [emailRecipients, setEmailRecipients] = useState([]);
  const [recipientEmail, setRecipientEmail] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isAddingRecipient, setIsAddingRecipient] = useState(false);
  const [isSendingEmail, setIsSendingEmail] = useState(false);

  async function loadSnapshots() {
    const data = await getWeeklySnapshots(token);
    setLatest(data.latest);
    setSnapshots(data.snapshots);
  }

  async function loadReportControls() {
    const [types, runData] = await Promise.all([getReportTypes(token), getReportRuns(token)]);
    setReportTypes(types);
    setSelectedReportType((current) => current || types[0]?.value || "");
    setReportRuns(runData.runs);
  }

  async function loadEmailRecipients() {
    const data = await getEmailRecipients(token);
    setEmailRecipients(data.recipients);
  }

  useEffect(() => {
    Promise.all([loadSnapshots(), loadReportControls(), loadEmailRecipients()]).catch((loadError) =>
      setError(loadError.message || "Weekly reports could not load.")
    );
  }, [token]);

  async function handleGenerate() {
    setIsGenerating(true);
    setMessage("");
    setError("");
    try {
      const data = await generateWeeklySnapshot(token);
      setLatest(data);
      setMessage(
        `Snapshot generated for ${formatDate(data.current_snapshot.week_start_date)} to ${formatDate(
          data.current_snapshot.week_end_date
        )}.`
      );
      await loadSnapshots();
    } catch (generateError) {
      setError(generateError.message || "Weekly snapshot could not be generated.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleDownloadReport() {
    if (!selectedReportType) {
      setError("Choose a report first.");
      return;
    }

    setIsExporting(true);
    setMessage("");
    setError("");
    try {
      const result = await downloadReportExcel({ token, reportType: selectedReportType });
      const url = URL.createObjectURL(result.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setMessage(`Excel report created: ${result.filename}`);
      await loadReportControls();
    } catch (downloadError) {
      setError(downloadError.message || "Report could not be created.");
    } finally {
      setIsExporting(false);
    }
  }

  async function handleAddRecipient(event) {
    event.preventDefault();
    setIsAddingRecipient(true);
    setMessage("");
    setError("");
    try {
      await createEmailRecipient({ token, email: recipientEmail, name: recipientName });
      setRecipientEmail("");
      setRecipientName("");
      setMessage("Email recipient added.");
      await loadEmailRecipients();
    } catch (recipientError) {
      setError(recipientError.message || "Email recipient could not be added.");
    } finally {
      setIsAddingRecipient(false);
    }
  }

  async function handleRecipientActiveChange(recipient, isActive) {
    setMessage("");
    setError("");
    try {
      await updateEmailRecipient({
        token,
        recipientId: recipient.id,
        name: recipient.name,
        isActive,
      });
      await loadEmailRecipients();
    } catch (recipientError) {
      setError(recipientError.message || "Email recipient could not be updated.");
    }
  }

  async function handleSendWeeklyEmail() {
    setIsSendingEmail(true);
    setMessage("");
    setError("");
    try {
      const result = await sendWeeklyEmail(token);
      setMessage(
        `Weekly email sent to ${result.recipient_count} recipient(s) with ${result.attachment_count} attachment(s).`
      );
      await loadReportControls();
    } catch (sendError) {
      setError(sendError.message || "Weekly email could not be sent.");
      await loadReportControls().catch(() => undefined);
    } finally {
      setIsSendingEmail(false);
    }
  }

  const summary = latest?.summary;
  const currentSnapshot = latest?.current_snapshot;
  const previousSnapshot = latest?.previous_snapshot;

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Weekly Reports</h2>
          <p>Weekly snapshot and movement tracking.</p>
        </div>
        <FileSpreadsheet size={24} aria-hidden="true" />
      </div>

      <div className="weekly-actions">
        <button className="primary-button" disabled={isGenerating} onClick={handleGenerate} type="button">
          <RefreshCw size={18} aria-hidden="true" />
          {isGenerating ? "Generating" : "Generate snapshot"}
        </button>
        <span>
          {currentSnapshot
            ? `${formatDate(currentSnapshot.week_start_date)} to ${formatDate(currentSnapshot.week_end_date)}`
            : "No snapshot generated yet"}
        </span>
      </div>

      <div className="report-export-panel">
        <label>
          Excel report
          <select value={selectedReportType} onChange={(event) => setSelectedReportType(event.target.value)}>
            {reportTypes.map((reportType) => (
              <option key={reportType.value} value={reportType.value}>
                {reportType.label}
              </option>
            ))}
          </select>
        </label>
        <button className="primary-button" disabled={isExporting || !selectedReportType} onClick={handleDownloadReport} type="button">
          <FileSpreadsheet size={18} aria-hidden="true" />
          {isExporting ? "Creating" : "Create Excel"}
        </button>
      </div>

      <div className="email-report-panel">
        <form className="recipient-form" onSubmit={handleAddRecipient}>
          <label>
            Recipient email
            <input
              onChange={(event) => setRecipientEmail(event.target.value)}
              required
              type="email"
              value={recipientEmail}
            />
          </label>
          <label>
            Name
            <input onChange={(event) => setRecipientName(event.target.value)} type="text" value={recipientName} />
          </label>
          <button className="primary-button" disabled={isAddingRecipient} type="submit">
            <Upload size={18} aria-hidden="true" />
            {isAddingRecipient ? "Adding" : "Add recipient"}
          </button>
        </form>
        <button className="primary-button" disabled={isSendingEmail} onClick={handleSendWeeklyEmail} type="button">
          <FileSpreadsheet size={18} aria-hidden="true" />
          {isSendingEmail ? "Sending" : "Send weekly email"}
        </button>
      </div>

      {message ? <p className="form-success">{message}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      <div className="section-heading">
        <h3>Email recipients</h3>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Email</th>
              <th>Name</th>
              <th>Status</th>
              <th>Added</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            {emailRecipients.length ? (
              emailRecipients.map((recipient) => (
                <tr key={recipient.id}>
                  <td>{recipient.email}</td>
                  <td>{recipient.name || "-"}</td>
                  <td>
                    <span className={`status-pill ${recipient.is_active ? "status-active" : "status-inactive"}`}>
                      {recipient.is_active ? "active" : "inactive"}
                    </span>
                  </td>
                  <td>{formatDateTime(recipient.created_at)}</td>
                  <td>
                    <input
                      checked={recipient.is_active}
                      onChange={(event) => handleRecipientActiveChange(recipient, event.target.checked)}
                      type="checkbox"
                    />
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5">No email recipients yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="summary-strip summary-strip-wide">
        <div>
          <span>Movements</span>
          <strong>{summary?.movement_count ?? 0}</strong>
        </div>
        <div>
          <span>New bookings</span>
          <strong>{summary?.new_bookings ?? 0}</strong>
        </div>
        <div>
          <span>Cancelled</span>
          <strong>{summary?.cancelled_bookings ?? 0}</strong>
        </div>
        <div>
          <span>Completed</span>
          <strong>{summary?.completed_bookings ?? 0}</strong>
        </div>
        <div>
          <span>Value changes</span>
          <strong>{summary?.changed_booking_value ?? 0}</strong>
        </div>
        <div>
          <span>Supplier cost</span>
          <strong>{summary?.changed_supplier_cost ?? 0}</strong>
        </div>
        <div>
          <span>Customer payment</span>
          <strong>{summary?.changed_payment_position ?? 0}</strong>
        </div>
        <div>
          <span>Supplier payment</span>
          <strong>{summary?.changed_supplier_payment_position ?? 0}</strong>
        </div>
        <div>
          <span>Refund</span>
          <strong>{summary?.changed_refund_position ?? 0}</strong>
        </div>
        <div>
          <span>Commission</span>
          <strong>{summary?.changed_commission_position ?? 0}</strong>
        </div>
        <div>
          <span>ATOL</span>
          <strong>{summary?.changed_atol_status ?? 0}</strong>
        </div>
        <div>
          <span>Previous snapshot</span>
          <strong>{previousSnapshot ? formatDate(previousSnapshot.week_start_date) : "-"}</strong>
        </div>
      </div>

      <div className="section-heading">
        <h3>Movement report</h3>
        <p>Current weekly snapshot compared with the previous snapshot.</p>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Movement</th>
              <th>Field</th>
              <th>Previous</th>
              <th>Current</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {latest?.movements?.length ? (
              latest.movements.map((movement, index) => (
                <tr key={`${movement.booking_ref}-${movement.field_name}-${index}`}>
                  <td>{movement.booking_ref}</td>
                  <td>
                    <span className={`status-pill status-${movement.movement_type}`}>
                      {formatStatusLabel(movement.movement_type)}
                    </span>
                  </td>
                  <td>{formatStatusLabel(movement.field_name)}</td>
                  <td>{movement.previous_value || "-"}</td>
                  <td>{movement.current_value || "-"}</td>
                  <td>{movement.description}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="6">
                  {previousSnapshot ? "No week-on-week movement found." : "Generate at least two weekly snapshots to compare movement."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="section-heading">
        <h3>Current snapshot bookings</h3>
        <p>{currentSnapshot ? `${currentSnapshot.booking_count} booking(s) captured.` : "No current snapshot."}</p>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Status</th>
              <th>Gross Value</th>
              <th>Supplier Nett</th>
              <th>Customer Paid</th>
              <th>Card Fees</th>
              <th>Supplier Paid</th>
              <th>Refunds Due</th>
              <th>Refunds Paid</th>
              <th>Commission Due</th>
              <th>Trust Balance</th>
              <th>ATOL</th>
            </tr>
          </thead>
          <tbody>
            {latest?.bookings?.length ? (
              latest.bookings.map((booking) => (
                <tr key={booking.booking_ref}>
                  <td>{booking.booking_ref}</td>
                  <td>{booking.booking_status || "-"}</td>
                  <td>{formatMoney(booking.gross_booking_value)}</td>
                  <td>{formatMoney(booking.expected_supplier_nett)}</td>
                  <td>{formatMoney(booking.customer_payments_total)}</td>
                  <td>{formatMoney(booking.card_fees_total)}</td>
                  <td>{formatMoney(booking.supplier_payments_total)}</td>
                  <td>{formatMoney(booking.refunds_due_total)}</td>
                  <td>{formatMoney(booking.refunds_paid_total)}</td>
                  <td>{formatMoney(booking.commission_due_total)}</td>
                  <td>{formatMoney(booking.calculated_trust_balance)}</td>
                  <td>{booking.atol_required ? "Required" : "Not required"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="12">No snapshot bookings yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="section-heading">
        <h3>Report run history</h3>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Report</th>
              <th>Status</th>
              <th>Started</th>
              <th>Finished</th>
              <th>File</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {reportRuns.length ? (
              reportRuns.map((run) => (
                <tr key={run.id}>
                  <td>{formatStatusLabel(run.report_type)}</td>
                  <td>
                    <span className={`status-pill status-${run.status}`}>{formatStatusLabel(run.status)}</span>
                  </td>
                  <td>{formatDateTime(run.started_at)}</td>
                  <td>{formatDateTime(run.finished_at)}</td>
                  <td>{run.output_filename || "-"}</td>
                  <td>{run.error_summary || "-"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="6">No report runs yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="section-heading">
        <h3>Snapshot history</h3>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Week Start</th>
              <th>Week End</th>
              <th>Status</th>
              <th>Bookings</th>
              <th>Generated</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.length ? (
              snapshots.map((snapshot) => (
                <tr key={snapshot.id}>
                  <td>{formatDate(snapshot.week_start_date)}</td>
                  <td>{formatDate(snapshot.week_end_date)}</td>
                  <td>
                    <span className={`status-pill status-${snapshot.status}`}>
                      {formatStatusLabel(snapshot.status)}
                    </span>
                  </td>
                  <td>{snapshot.booking_count}</td>
                  <td>{formatDateTime(snapshot.generated_at)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5">No weekly snapshots yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SettingsPage({ token }) {
  const [settingsStatus, setSettingsStatus] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getSettingsStatus(token)
      .then((data) => {
        setSettingsStatus(data);
        setError("");
      })
      .catch((loadError) => setError(loadError.message || "Settings could not load."));
  }, [token]);

  const felloh = settingsStatus?.felloh || {};
  const traveltek = settingsStatus?.traveltek || {};
  const email = settingsStatus?.email || {};

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Settings</h2>
          <p>Safe configuration check. Private keys and passwords are hidden.</p>
        </div>
        <ShieldCheck size={24} aria-hidden="true" />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="summary-strip summary-strip-wide">
        <div>
          <span>Environment</span>
          <strong>{settingsStatus?.environment || "Loading"}</strong>
        </div>
        <div>
          <span>Database</span>
          <strong>{settingsStatus ? (settingsStatus.database_configured ? "Configured" : "Needs setting") : "Loading"}</strong>
        </div>
        <div>
          <span>Felloh / SINGs API</span>
          <strong>{settingsStatus ? (felloh.configured ? "Configured" : "Needs setting") : "Loading"}</strong>
        </div>
        <div>
          <span>Traveltek API</span>
          <strong>{settingsStatus ? (traveltek.configured ? "Configured" : "Needs setting") : "Loading"}</strong>
        </div>
        <div>
          <span>Outlook email</span>
          <strong>{settingsStatus ? (email.configured ? "Configured" : "Needs setting") : "Loading"}</strong>
        </div>
        <div>
          <span>Upload limit</span>
          <strong>{settingsStatus ? `${settingsStatus.max_upload_size_mb} MB` : "Loading"}</strong>
        </div>
      </div>

      <div className="section-heading">
        <h3>Connection checks</h3>
        <p>This tells you what is set up in Render without exposing secret values.</p>
      </div>

      <div className="progress-list">
        <span>Database connection</span>
        <strong>
          <ConfigStatus isConfigured={settingsStatus?.database_configured} />
        </strong>
        <span>Frontend URL</span>
        <strong>
          <ConfigStatus isConfigured={settingsStatus?.frontend_url_configured} />
        </strong>
        <span>Felloh base URL</span>
        <strong>
          <ConfigStatus isConfigured={felloh.base_url_configured} />
        </strong>
        <span>Felloh public key</span>
        <strong>
          <ConfigStatus isConfigured={felloh.public_key_configured} />
        </strong>
        <span>Felloh private key</span>
        <strong>
          <ConfigStatus isConfigured={felloh.private_key_configured} />
        </strong>
        <span>Felloh organisation ID</span>
        <strong>
          <ConfigStatus isConfigured={felloh.organisation_id_configured} />
        </strong>
        <span>Traveltek base URL</span>
        <strong>
          <ConfigStatus isConfigured={traveltek.base_url_configured} />
        </strong>
        <span>Traveltek secure detail URL</span>
        <strong>
          <ConfigStatus isConfigured={traveltek.secure_base_url_configured} />
        </strong>
        <span>Traveltek username</span>
        <strong>
          <ConfigStatus isConfigured={traveltek.username_configured} />
        </strong>
        <span>Traveltek password</span>
        <strong>
          <ConfigStatus isConfigured={traveltek.password_configured} />
        </strong>
        <span>Traveltek sitename / SID</span>
        <strong>
          <ConfigStatus isConfigured={traveltek.sitename_configured} />
        </strong>
        <span>Traveltek calls per run</span>
        <strong>{settingsStatus ? traveltek.max_calls_per_run : "Loading"}</strong>
        <span>Outlook SMTP host</span>
        <strong>
          <ConfigStatus isConfigured={email.host_configured} />
        </strong>
        <span>Outlook sender email</span>
        <strong>
          <ConfigStatus isConfigured={email.from_email_configured} />
        </strong>
        <span>Outlook username</span>
        <strong>
          <ConfigStatus isConfigured={email.username_configured} />
        </strong>
        <span>Outlook password</span>
        <strong>
          <ConfigStatus isConfigured={email.password_configured} />
        </strong>
        <span>Email security</span>
        <strong>{email.use_tls ? "TLS on" : "TLS off"}</strong>
        <span>Email port</span>
        <strong>{settingsStatus ? email.port : "Loading"}</strong>
        <span>Login session length</span>
        <strong>{settingsStatus ? `${settingsStatus.login_session_minutes} minutes` : "Loading"}</strong>
      </div>
    </section>
  );
}

function DashboardHome({ dashboardStatus, health, token }) {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getExceptions(token, { status: "all", severity: "all" })
      .then((data) => {
        setSummary(data.summary);
        setError("");
      })
      .catch((loadError) => setError(loadError.message || "Exceptions could not load."));
  }, [token]);

  const openExceptions = (summary?.open_count ?? 0) + (summary?.reviewing_count ?? 0);
  const bookingChecks = dashboardStatus?.booking_checks || {};
  const insurance = dashboardStatus?.insurance || {};

  return (
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
        <StatusCard icon={ShieldCheck} label="Access" value="Super Admin only" tone="success" />
        <StatusCard
          icon={CheckCircle2}
          label="Full booking matches"
          value={bookingChecks.fully_matched ?? 0}
          tone="success"
        />
        <StatusCard
          icon={XCircle}
          label="Booking check errors"
          value={bookingChecks.error_count ?? 0}
          tone={bookingChecks.error_count ? "warning" : "success"}
        />
        <StatusCard
          icon={Clock3}
          label="Awaiting imports"
          value={bookingChecks.awaiting_count ?? 0}
          tone={bookingChecks.awaiting_count ? "warning" : "success"}
        />
        <StatusCard
          icon={HandCoins}
          label="Active insurance cost"
          value={formatMoney(insurance.active_cost_total)}
          tone="neutral"
        />
        <StatusCard
          icon={CircleAlert}
          label="Insurance unmatched"
          value={insurance.unmatched_count ?? 0}
          tone={insurance.unmatched_count ? "warning" : "success"}
        />
        <StatusCard
          icon={AlertTriangle}
          label="Open exceptions"
          value={error ? "Unable to load" : openExceptions}
          tone={openExceptions ? "warning" : "success"}
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
          <span>Customer payments</span>
          <strong>SINGs/Singhs import ready</strong>
          <span>Refunds</span>
          <strong>Liability tracking ready</strong>
          <span>Agent commissions</span>
          <strong>True profit calculation ready</strong>
          <span>Bank transactions</span>
          <strong>Statement import ready</strong>
          <span>Trust reconciliation</span>
          <strong>Booking-level calculation ready</strong>
          <span>Exceptions</span>
          <strong>Automated review list ready</strong>
          <span>Weekly snapshots</span>
          <strong>Movement tracking ready</strong>
          <span>Agent access</span>
          <strong>Not included</strong>
        </div>
      </section>
    </>
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
  const [loginNotice, setLoginNotice] = useState("");

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
        setLoginNotice("Your login has expired. Please log in again.");
      });
  }, [token]);

  useEffect(() => {
    return onAuthExpired((event) => {
      clearStoredToken();
      setToken(null);
      setUser(null);
      setHealth(null);
      setDashboardStatus(null);
      setLoginNotice(event.detail?.message || "Your login has expired. Please log in again.");
    });
  }, []);

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
    setLoginNotice("");
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
      setLoginNotice("");
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
    return <LoginPage notice={loginNotice} onLogin={handleLogin} />;
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

        {activeView === "Booking Checks" ? (
          <BookingChecksPage token={token} />
        ) : activeView === "Upload Centre" ? (
          <UploadCentre token={token} />
        ) : activeView === "Bookings" ? (
          <BookingsPage token={token} />
        ) : activeView === "Traveltek Updates" ? (
          <TraveltekUpdatesPage token={token} />
        ) : activeView === "Supplier Payments TAPs" ? (
          <SupplierPaymentsPage token={token} source="taps" />
        ) : activeView === "Supplier Payments TT" ? (
          <SupplierPaymentsPage token={token} source="tt" />
        ) : activeView === "Customer Payments" ? (
          <CustomerPaymentsPage token={token} />
        ) : activeView === "Insurance Costs" ? (
          <InsuranceCostsPage token={token} />
        ) : activeView === "Refunds" ? (
          <RefundsPage token={token} />
        ) : activeView === "Agent Commissions" ? (
          <AgentCommissionsPage token={token} />
        ) : activeView === "Bank Transactions" ? (
          <BankTransactionsPage token={token} />
        ) : activeView === "Head Office Costs" ? (
          <HeadOfficeCostsPage token={token} />
        ) : activeView === "Trust Reconciliation" ? (
          <TrustReconciliationPage token={token} />
        ) : activeView === "Exceptions" ? (
          <ExceptionsPage token={token} />
        ) : activeView === "Weekly Reports" ? (
          <WeeklyReportsPage token={token} />
        ) : activeView === "Settings" ? (
          <SettingsPage token={token} />
        ) : (
          <DashboardHome dashboardStatus={dashboardStatus} health={health} token={token} />
        )}
      </section>
    </main>
  );
}
