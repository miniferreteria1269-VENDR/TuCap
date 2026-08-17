import { useEffect, useState } from "react";

import { addCapital, getCapitalEntries, getCapitalSummary, reverseCapitalEntry, withdrawCapital } from "../api";
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

function Dashboard() {
  const [summary, setSummary] = useState(emptySummary);
  const [showCapitalForm, setShowCapitalForm] = useState(false);
  const [showWithdrawalForm, setShowWithdrawalForm] = useState(false);
  const [error, setError] = useState("");
  const [entries, setEntries] = useState([]);
  const [reversalEntry, setReversalEntry] = useState(null);

  const loadSummary = async () => {
    try {
      const [nextSummary, nextEntries] = await Promise.all([getCapitalSummary(), getCapitalEntries()]);
      setSummary(nextSummary);
      setEntries(nextEntries);
      setError("");
    } catch (loadError) {
      setError(loadError.message);
    }
  };

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCapitalSummary(), getCapitalEntries()])
      .then(([result, movements]) => {
        if (!cancelled) {
          setSummary(result);
          setEntries(movements);
        }
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const saveCapital = async (payload) => {
    await addCapital(payload);
    setShowCapitalForm(false);
    await loadSummary();
  };

  const saveWithdrawal = async (payload) => {
    await withdrawCapital(payload);
    setShowWithdrawalForm(false);
    await loadSummary();
  };

  const reverseEntry = async (payload) => {
    await reverseCapitalEntry(reversalEntry.id, payload);
    setReversalEntry(null);
    await loadSummary();
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
