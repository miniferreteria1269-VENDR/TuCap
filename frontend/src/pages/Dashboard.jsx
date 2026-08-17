import { useEffect, useState } from "react";

import { addCapital, getCapitalSummary, withdrawCapital } from "../api";
import AddCapitalModal from "../components/AddCapitalModal";
import MetricCard from "../components/MetricCard";
import WithdrawCapitalModal from "../components/WithdrawCapitalModal";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

const emptySummary = {
  capital_on_hand: 0,
  principal_receivable: 0,
  accrued_interest_receivable: 0,
  active_loans: 0,
  collected_this_month: 0,
};

function Dashboard() {
  const [summary, setSummary] = useState(emptySummary);
  const [showCapitalForm, setShowCapitalForm] = useState(false);
  const [showWithdrawalForm, setShowWithdrawalForm] = useState(false);
  const [error, setError] = useState("");

  const loadSummary = async () => {
    try {
      setSummary(await getCapitalSummary());
      setError("");
    } catch (loadError) {
      setError(loadError.message);
    }
  };

  useEffect(() => {
    let cancelled = false;
    getCapitalSummary()
      .then((result) => {
        if (!cancelled) setSummary(result);
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

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Actividad</p>
            <h3>Próximos cobros</h3>
          </div>
          <button className="text-button" type="button">Ver todos</button>
        </div>
        <div className="empty-state">
          <span className="empty-icon" aria-hidden="true">✓</span>
          <strong>Todo al día</strong>
          <p>Los próximos cobros aparecerán aquí.</p>
        </div>
      </section>

      {showCapitalForm && (
        <AddCapitalModal onClose={() => setShowCapitalForm(false)} onSave={saveCapital} />
      )}
      {showWithdrawalForm && (
        <WithdrawCapitalModal available={summary.capital_on_hand} onClose={() => setShowWithdrawalForm(false)} onSave={saveWithdrawal} />
      )}
    </>
  );
}

export default Dashboard;
