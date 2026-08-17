import { useEffect, useState } from "react";

import { getLoanDetail } from "../api";
import ClosedLoanActionModal from "./ClosedLoanActionModal";
import WriteOffModal from "./WriteOffModal";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });
const day = new Intl.DateTimeFormat("es-SV", { day: "numeric", month: "short", year: "numeric" });
const dateTime = new Intl.DateTimeFormat("es-SV", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
const statusLabels = { active: "Activo", paid: "Pagado", written_off: "Castigado" };

function formatDay(value) {
  return day.format(new Date(`${value}T12:00:00`));
}

function formatDateTime(value) {
  return dateTime.format(new Date(value));
}

function LoanDetailModal({ client, loan, onClose, onReceivePayment, onMutated }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [action, setAction] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getLoanDetail(loan.id)
      .then((result) => { if (!cancelled) setDetail(result); })
      .catch((loadError) => { if (!cancelled) setError(loadError.message); });
    return () => { cancelled = true; };
  }, [loan.id]);

  const current = detail || loan;
  const totalPending = Number(current.principal_outstanding || 0) + Number(current.accrued_interest || 0);

  const completeAction = (updated) => {
    setDetail(updated);
    setAction(null);
    onMutated?.();
  };

  if (action === "write-off") return <WriteOffModal client={client} loan={current} onClose={() => setAction(null)} onComplete={completeAction} />;
  if (action === "recovery" || action === "performance") return <ClosedLoanActionModal loan={current} mode={action} onClose={() => setAction(null)} onComplete={completeAction} />;

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="sheet-modal loan-detail-sheet" role="dialog" aria-modal="true" aria-labelledby="loan-detail-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading">
          <div><p className="eyebrow">{client.full_name}</p><h2 id="loan-detail-title">Detalle del préstamo</h2></div>
          <button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button>
        </div>

        <div className="loan-detail-hero">
          <div><span className={`status-pill ${current.status}`}>{statusLabels[current.status] || current.status}</span><small>Saldo total pendiente</small><strong>{currency.format(totalPending)}</strong></div>
          <span>{Number(current.monthly_interest_rate).toLocaleString("es-SV")}% mensual</span>
        </div>

        {error && <p className="form-error loan-detail-error">{error}</p>}
        {!detail && !error && <div className="detail-loading">Cargando historial…</div>}

        {detail && (
          <>
            <div className="loan-detail-metrics">
              <article><span>Capital pendiente</span><strong>{currency.format(detail.principal_outstanding)}</strong></article>
              <article><span>Interés pendiente</span><strong>{currency.format(detail.accrued_interest)}</strong></article>
              <article><span>Total cobrado</span><strong>{currency.format(detail.total_collected)}</strong></article>
              <article><span>Interés cobrado</span><strong>{currency.format(detail.total_interest_collected)}</strong></article>
            </div>

            {detail.performance && (
              <section className={`performance-card ${detail.performance.economic_outcome}`}>
                <div className="performance-heading">
                  <div><p className="eyebrow">Desempeño final</p><h3>{detail.performance.contract_fulfilled ? "Contrato cumplido" : "Contrato incumplido"}</h3></div>
                  <strong>{detail.performance.economic_outcome === "loss" ? "Pérdida" : detail.performance.economic_outcome === "break_even" ? "Punto de equilibrio" : detail.status === "written_off" ? "Ganancia ajustada" : "Ganancia"}</strong>
                </div>
                <div className="economic-result"><span>Resultado económico</span><strong>{currency.format(detail.performance.economic_result)}</strong></div>
                <div className="performance-grid">
                  <div><span>Total recuperado</span><strong>{currency.format(detail.performance.total_recovered)}</strong></div>
                  <div><span>Pagos recibidos</span><strong>{currency.format(detail.performance.payments_collected)}</strong></div>
                  <div><span>Garantía recuperada</span><strong>{currency.format(detail.performance.collateral_recovered)}</strong></div>
                  <div><span>Promedio mensual</span><strong>{currency.format(detail.performance.average_monthly_result)}</strong></div>
                  <div><span>Duración</span><strong>{detail.performance.duration_days} días</strong></div>
                  <div><span>Pagos tardíos</span><strong>{detail.performance.late_payment_count}</strong></div>
                </div>
                {!detail.performance.contract_fulfilled && <div className="contract-shortfall"><span>Faltante contractual</span><strong>{currency.format(Number(detail.performance.principal_shortfall) + Number(detail.performance.interest_shortfall))}</strong><small>Capital {currency.format(detail.performance.principal_shortfall)} · Interés {currency.format(detail.performance.interest_shortfall)}</small></div>}
                {detail.performance.notes && <p className="performance-notes">{detail.performance.notes}</p>}
              </section>
            )}

            <section className="loan-detail-section">
              <p className="eyebrow">Condiciones</p>
              <dl className="loan-facts">
                <div><dt>Capital original</dt><dd>{currency.format(detail.original_principal)}</dd></div>
                <div><dt>Fecha del préstamo</dt><dd>{formatDay(detail.start_date)}</dd></div>
                <div><dt>Próximo interés</dt><dd>{formatDay(detail.next_interest_date)}</dd></div>
                <div><dt>Garantía</dt><dd>{detail.collateral_description || "—"}</dd></div>
                <div><dt>Valor estimado</dt><dd>{detail.collateral_estimated_value == null ? "—" : currency.format(detail.collateral_estimated_value)}</dd></div>
                <div><dt>Notas</dt><dd>{detail.notes || "—"}</dd></div>
              </dl>
            </section>

            <section className="loan-detail-section">
              <div className="history-heading"><div><p className="eyebrow">Cobros</p><h3>Historial de pagos</h3></div><span>{detail.payments.length}</span></div>
              {detail.payments.length === 0 ? <p className="history-empty">Todavía no hay pagos registrados.</p> : (
                <div className="payment-history-list">
                  {detail.payments.map((payment) => (
                    <article key={payment.id}>
                      <div><strong>{currency.format(payment.amount_received)}</strong><time>{formatDateTime(payment.received_at)}</time></div>
                      <dl><div><dt>Interés</dt><dd>{currency.format(payment.amount_to_interest)}</dd></div><div><dt>Capital</dt><dd>{currency.format(payment.amount_to_principal)}</dd></div></dl>
                      {payment.notes && <p>{payment.notes}</p>}
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="loan-detail-section">
              <div className="history-heading"><div><p className="eyebrow">Cálculo</p><h3>Cargos de interés</h3></div><span>{detail.interest_accruals.length}</span></div>
              <div className="accrual-history-list">
                {detail.interest_accruals.map((accrual) => (
                  <div key={accrual.id}><span>{formatDay(accrual.cycle_date)}<small>Sobre {currency.format(accrual.principal_basis)} al {Number(accrual.monthly_rate).toLocaleString("es-SV")}%</small></span><strong>{currency.format(accrual.amount)}</strong></div>
                ))}
              </div>
            </section>
          </>
        )}

        {current.status === "active" && <div className="loan-detail-actions"><button className="write-off-button" type="button" onClick={() => setAction("write-off")}>Castigar préstamo</button><button className="primary-button" type="button" onClick={() => onReceivePayment(current)}>Recibir pago</button></div>}
        {current.status !== "active" && <div className="loan-detail-actions closed-actions"><button className="loan-detail-button" type="button" onClick={() => setAction("performance")}>Editar desempeño</button>{current.status === "written_off" && <button className="primary-button" type="button" onClick={() => setAction("recovery")}>Registrar recuperación</button>}</div>}
      </section>
    </div>
  );
}

export default LoanDetailModal;
