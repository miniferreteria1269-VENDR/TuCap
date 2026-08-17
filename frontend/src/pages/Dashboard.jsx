import { useEffect, useState } from "react";

import { addCapital, getCapitalEntries, getCapitalReport, getCapitalSummary, reverseCapitalEntry, withdrawCapital } from "../api";
import AddCapitalModal from "../components/AddCapitalModal";
import MetricCard from "../components/MetricCard";
import ReversalModal from "../components/ReversalModal";
import WithdrawCapitalModal from "../components/WithdrawCapitalModal";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

const emptySummary = {
  capital_on_hand: 0,
  principal_receivable: 0,
  accrued_interest_receivable: 0,
  active_loans: 0,
  collected_this_month: 0,
};

const movementLabels = {
  capital_deposit: "Capital agregado",
  withdrawal: "Retiro de capital",
  collateral_recovery: "Recuperación de garantía",
  adjustment: "Contrapartida de anulación",
};

const dateTime = new Intl.DateTimeFormat("es-SV", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
const shortDate = new Intl.DateTimeFormat("es-SV", { day: "numeric", month: "short", year: "numeric" });

function localDate(value = new Date()) {
  const adjusted = new Date(value);
  adjusted.setMinutes(adjusted.getMinutes() - adjusted.getTimezoneOffset());
  return adjusted.toISOString().slice(0, 10);
}

function rangeFor(preset) {
  const end = new Date();
  const start = new Date(end);
  if (preset === "today") return { from: localDate(end), to: localDate(end) };
  if (preset === "7days") start.setDate(start.getDate() - 6);
  if (preset === "30days") start.setDate(start.getDate() - 29);
  if (preset === "month") start.setDate(1);
  return { from: localDate(start), to: localDate(end) };
}

const initialRange = rangeFor("month");
const emptyReport = {
  payments_collected: 0,
  interest_collected: 0,
  principal_collected: 0,
  capital_lent: 0,
  new_loans: 0,
  capital_deposited: 0,
  capital_withdrawn: 0,
  collateral_recovered: 0,
  loans_closed: 0,
  loans_paid: 0,
  loans_written_off: 0,
  realized_economic_result: 0,
};

function Dashboard() {
  const [summary, setSummary] = useState(emptySummary);
  const [showCapitalForm, setShowCapitalForm] = useState(false);
  const [showWithdrawalForm, setShowWithdrawalForm] = useState(false);
  const [error, setError] = useState("");
  const [entries, setEntries] = useState([]);
  const [reversalEntry, setReversalEntry] = useState(null);
  const [rangePreset, setRangePreset] = useState("month");
  const [dateFrom, setDateFrom] = useState(initialRange.from);
  const [dateTo, setDateTo] = useState(initialRange.to);
  const [report, setReport] = useState(emptyReport);
  const [reportLoading, setReportLoading] = useState(true);

  const loadDashboard = async () => {
    try {
      const [nextSummary, nextEntries, nextReport] = await Promise.all([
        getCapitalSummary(),
        getCapitalEntries(),
        getCapitalReport(dateFrom, dateTo),
      ]);
      setSummary(nextSummary);
      setEntries(nextEntries);
      setReport(nextReport);
      setReportLoading(false);
      setError("");
    } catch (loadError) {
      setError(loadError.message);
      setReportLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCapitalSummary(), getCapitalEntries(), getCapitalReport(dateFrom, dateTo)])
      .then(([result, movements, periodReport]) => {
        if (!cancelled) {
          setSummary(result);
          setEntries(movements);
          setReport(periodReport);
        }
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message);
      })
      .finally(() => {
        if (!cancelled) setReportLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dateFrom, dateTo]);

  const choosePreset = (preset) => {
    const nextRange = rangeFor(preset);
    setReportLoading(true);
    setRangePreset(preset);
    setDateFrom(nextRange.from);
    setDateTo(nextRange.to);
  };

  const saveCapital = async (payload) => {
    await addCapital(payload);
    setShowCapitalForm(false);
    await loadDashboard();
  };

  const saveWithdrawal = async (payload) => {
    await withdrawCapital(payload);
    setShowWithdrawalForm(false);
    await loadDashboard();
  };

  const reverseEntry = async (payload) => {
    await reverseCapitalEntry(reversalEntry.id, payload);
    setReversalEntry(null);
    await loadDashboard();
  };

  return (
    <>
      <section className="hero-card">
        <p className="eyebrow">Capital disponible</p>
        <h2>{currency.format(summary.capital_on_hand)}</h2>
        <p className="hero-detail">
          {Number(summary.capital_on_hand) === 0
            ? "Listo para registrar el capital inicial"
            : "Disponible después de préstamos, cobros y movimientos"}
        </p>
        <div className="hero-actions">
          <button className="secondary-button" type="button" onClick={() => setShowCapitalForm(true)}>Agregar capital</button>
          <button className="withdraw-button" disabled={Number(summary.capital_on_hand) <= 0} type="button" onClick={() => setShowWithdrawalForm(true)}>Retirar</button>
        </div>
      </section>

      {error && <p className="dashboard-error">No se pudo actualizar el resumen: {error}</p>}

      <section className="metric-grid" aria-label="Resumen de cartera">
        <MetricCard label="Por cobrar" value={currency.format(summary.principal_receivable)} detail="Capital pendiente" />
        <MetricCard label="Interés acumulado" value={currency.format(summary.accrued_interest_receivable)} detail="Pendiente de cobro" tone="accent" />
        <MetricCard label="Préstamos activos" value={summary.active_loans} detail="Cartera abierta" />
        <MetricCard label="Cobrado este mes" value={currency.format(summary.collected_this_month)} detail="Interés + capital" />
      </section>

      <section className="section-block period-report">
        <div className="section-heading">
          <div><p className="eyebrow">Análisis</p><h3>Actividad del período</h3></div>
          <span className="period-range">{shortDate.format(new Date(`${dateFrom}T12:00:00`))} – {shortDate.format(new Date(`${dateTo}T12:00:00`))}</span>
        </div>

        <div className="period-presets" aria-label="Seleccionar período">
          <button className={rangePreset === "today" ? "active" : ""} type="button" onClick={() => choosePreset("today")}>Hoy</button>
          <button className={rangePreset === "7days" ? "active" : ""} type="button" onClick={() => choosePreset("7days")}>7 días</button>
          <button className={rangePreset === "30days" ? "active" : ""} type="button" onClick={() => choosePreset("30days")}>30 días</button>
          <button className={rangePreset === "month" ? "active" : ""} type="button" onClick={() => choosePreset("month")}>Este mes</button>
          <button className={rangePreset === "custom" ? "active" : ""} type="button" onClick={() => setRangePreset("custom")}>Personalizado</button>
        </div>

        {rangePreset === "custom" && <div className="custom-period"><label><span>Desde</span><input max={dateTo} type="date" value={dateFrom} onChange={(event) => { setReportLoading(true); setDateFrom(event.target.value); }} /></label><label><span>Hasta</span><input min={dateFrom} type="date" value={dateTo} onChange={(event) => { setReportLoading(true); setDateTo(event.target.value); }} /></label></div>}

        {reportLoading ? <div className="period-loading">Calculando actividad…</div> : <>
          <div className="period-collection-hero">
            <div><span>Total cobrado</span><strong>{currency.format(report.payments_collected)}</strong></div>
            <dl><div><dt>Interés</dt><dd>{currency.format(report.interest_collected)}</dd></div><div><dt>Capital</dt><dd>{currency.format(report.principal_collected)}</dd></div></dl>
          </div>

          <div className="period-metric-grid">
            <article><span>Capital prestado</span><strong>{currency.format(report.capital_lent)}</strong><small>{report.new_loans} préstamos nuevos</small></article>
            <article><span>Capital agregado</span><strong>{currency.format(report.capital_deposited)}</strong><small>Aportes a la caja</small></article>
            <article><span>Retiros</span><strong>{currency.format(report.capital_withdrawn)}</strong><small>Uso personal u otros</small></article>
            <article><span>Garantías recuperadas</span><strong>{currency.format(report.collateral_recovered)}</strong><small>Ingresadas en el período</small></article>
          </div>

          <div className={`period-result ${Number(report.realized_economic_result) < 0 ? "loss" : "gain"}`}>
            <div><span>Resultado de préstamos cerrados</span><small>{report.loans_closed} cerrados · {report.loans_paid} pagados · {report.loans_written_off} castigados</small></div>
            <strong>{currency.format(report.realized_economic_result)}</strong>
          </div>
          <p className="period-note">El resultado toma la recuperación total actual de los préstamos cuya fecha de cierre cae dentro del período.</p>
        </>}
      </section>

      <section className="section-block capital-activity">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Actividad</p>
            <h3>Movimientos de capital</h3>
          </div>
        </div>
        {entries.length === 0 ? <div className="empty-state compact"><strong>Sin movimientos todavía</strong><p>Los depósitos, retiros y recuperaciones aparecerán aquí.</p></div> : <div className="capital-entry-list">{entries.map((entry) => <article className={entry.reversed_at ? "reversed-record" : ""} key={entry.id}><div className="capital-entry-main"><div><strong>{movementLabels[entry.entry_type] || entry.entry_type}</strong><time>{dateTime.format(new Date(entry.occurred_at))}</time></div><strong className={Number(entry.amount) < 0 ? "negative" : "positive"}>{Number(entry.amount) >= 0 ? "+" : "−"}{currency.format(Math.abs(Number(entry.amount)))}</strong></div>{entry.notes && <p>{entry.notes}</p>}{entry.reversed_at ? <div className="reversal-stamp"><strong>Anulado</strong><span>{entry.reversal_reason}</span></div> : entry.reversible && <button className="reverse-record-button" type="button" onClick={() => setReversalEntry(entry)}>Anular movimiento</button>}</article>)}</div>}
      </section>

      {showCapitalForm && (
        <AddCapitalModal onClose={() => setShowCapitalForm(false)} onSave={saveCapital} />
      )}
      {showWithdrawalForm && (
        <WithdrawCapitalModal available={summary.capital_on_hand} onClose={() => setShowWithdrawalForm(false)} onSave={saveWithdrawal} />
      )}
      {reversalEntry && <ReversalModal amount={reversalEntry.amount} description={movementLabels[reversalEntry.entry_type] || reversalEntry.entry_type} onClose={() => setReversalEntry(null)} onConfirm={reverseEntry} />}
    </>
  );
}

export default Dashboard;
