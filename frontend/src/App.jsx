import {
  Activity,
  Banknote,
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
  ShieldCheck,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  clearStoredToken,
  getAgentCommissions,
  getApiHealth,
  getBankTransactions,
  getBookings,
  getCurrentUser,
  getCustomerPayments,
  getDashboardStatus,
  getRefunds,
  getSupplierPayments,
  getStoredToken,
  getTrustReconciliation,
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
  { label: "Customer Payments", enabled: true },
  { label: "Refunds", enabled: true },
  { label: "Agent Commissions", enabled: true },
  { label: "Bank Transactions", enabled: true },
  { label: "Trust Reconciliation", enabled: true },
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

function CustomerPaymentsPage({ token }) {
  const [payments, setPayments] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getCustomerPayments(token)
      .then((data) => {
        setPayments(data.payments);
        setSummary(data.summary);
      })
      .catch((loadError) => setError(loadError.message || "Customer payments could not load."));
  }, [token]);

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

      <div className="summary-strip">
        <div>
          <span>Rows</span>
          <strong>{summary?.total_rows ?? 0}</strong>
        </div>
        <div>
          <span>Gross customer payments</span>
          <strong>{formatMoney(summary?.gross_total)}</strong>
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

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Payment Date</th>
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
            {payments.length ? (
              payments.map((payment) => (
                <tr key={payment.id}>
                  <td>{formatDate(payment.payment_date)}</td>
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
                <td colSpan="13">No customer payment rows imported yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BankTransactionsPage({ token }) {
  const [transactions, setTransactions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getBankTransactions(token)
      .then((data) => {
        setTransactions(data.transactions);
        setSummary(data.summary);
      })
      .catch((loadError) => setError(loadError.message || "Bank transactions could not load."));
  }, [token]);

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

      <div className="summary-strip">
        <div>
          <span>Rows</span>
          <strong>{summary?.total_rows ?? 0}</strong>
        </div>
        <div>
          <span>Latest trust balance</span>
          <strong>{formatMoney(summary?.latest_trust_balance)}</strong>
        </div>
        <div>
          <span>Balance date</span>
          <strong>{formatDate(summary?.latest_trust_balance_date)}</strong>
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
          <strong>{summary?.latest_trust_balance ? "Ready" : "Awaiting statement"}</strong>
        </div>
      </div>

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
            {transactions.length ? (
              transactions.map((transaction) => (
                <tr key={transaction.id}>
                  <td>{formatDate(transaction.transaction_date)}</td>
                  <td>{transaction.description || "-"}</td>
                  <td>{formatMoney(transaction.money_in)}</td>
                  <td>{formatMoney(transaction.money_out)}</td>
                  <td>{formatMoney(transaction.balance)}</td>
                  <td>{transaction.account_type || "-"}</td>
                  <td>{transaction.transaction_reference || "-"}</td>
                  <td>
                    <span className={`status-pill status-${transaction.match_status}`}>
                      {formatStatusLabel(transaction.match_status)}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="8">No bank statement rows imported yet.</td>
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
        <p>Gross value minus supplier nett, payment fees, commission and refunds.</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Booking Ref</th>
              <th>Last Name</th>
              <th>Gross Value</th>
              <th>Supplier Nett</th>
              <th>Payment Fees</th>
              <th>Commission</th>
              <th>Refunds</th>
              <th>True Profit</th>
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
                  <td>{formatMoney(profit.payment_fees)}</td>
                  <td>{formatMoney(profit.agent_commission)}</td>
                  <td>{formatMoney(profit.refunds_adjustments)}</td>
                  <td>{formatMoney(profit.true_booking_profit)}</td>
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
                <td colSpan="11">No bookings are ready for true profit calculation yet.</td>
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
        ) : activeView === "Customer Payments" ? (
          <CustomerPaymentsPage token={token} />
        ) : activeView === "Refunds" ? (
          <RefundsPage token={token} />
        ) : activeView === "Agent Commissions" ? (
          <AgentCommissionsPage token={token} />
        ) : activeView === "Bank Transactions" ? (
          <BankTransactionsPage token={token} />
        ) : activeView === "Trust Reconciliation" ? (
          <TrustReconciliationPage token={token} />
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
