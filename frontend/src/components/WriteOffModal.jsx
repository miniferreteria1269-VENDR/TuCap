import { useState } from "react";

import { writeOffLoan } from "../api";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

function today() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
}

function WriteOffModal({ client, loan, onClose, onComplete }) {
  const [closedDate, setClosedDate] = useState(today());
  const [recovery, setRecovery] = useState("0");
  const [lateCount, setLateCount] = useState("0");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const collected = Number(loan.total_collected || 0);
  const recovered = Number(recovery) || 0;
  const result = collected + recovered - Number(loan.original_principal);

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const detail = await writeOffLoan(loan.id, {
        closed_at: `${closedDate}T12:00:00Z`,
        collateral_recovery_amount: recovery || "0",
        late_payment_count: Number(lateCount) || 0,
        notes: notes.trim() || null,
      });
      onComplete(detail);
    } catch (saveError) {
      setError(saveError.message);
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="sheet-modal compact-sheet" role="dialog" aria-modal="true" aria-labelledby="write-off-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading"><div><p className="eyebrow">{client.full_name}</p><h2 id="write-off-title">Castigar préstamo</h2></div><button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button></div>
        <form className="client-form" onSubmit={submit}>
          <div className="payment-balances"><article><span>Capital pendiente</span><strong>{currency.format(loan.principal_outstanding)}</strong></article><article><span>Interés pendiente</span><strong>{currency.format(loan.accrued_interest)}</strong></article></div>
          <label className="field full-width"><span>Fecha de cierre</span><input min={loan.start_date} onChange={(event) => setClosedDate(event.target.value)} type="date" value={closedDate} /></label>
          <label className="field full-width"><span>Recuperación de garantía al cierre</span><div className="money-input"><span>$</span><input inputMode="decimal" min="0" onChange={(event) => setRecovery(event.target.value)} step="0.01" type="number" value={recovery} /></div><small>Déjalo en cero si la garantía se cobrará después.</small></label>
          <label className="field full-width"><span>Pagos tardíos</span><input inputMode="numeric" min="0" onChange={(event) => setLateCount(event.target.value)} step="1" type="number" value={lateCount} /></label>
          <div className={result < 0 ? "economic-preview loss" : "economic-preview gain"}><span>Resultado económico estimado</span><strong>{currency.format(result)}</strong><small>Cobros + garantía − capital originalmente prestado</small></div>
          <label className="field full-width"><span>Notas del cierre</span><textarea onChange={(event) => setNotes(event.target.value)} placeholder="Motivo, acuerdo o condición de la garantía" rows="2" value={notes} /></label>
          <p className="warning-note">El préstamo quedará cerrado contractualmente. Los saldos pendientes se conservarán como faltantes para el análisis.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="modal-actions"><button className="cancel-button" type="button" onClick={onClose}>Cancelar</button><button className="danger-button" disabled={saving} type="submit">{saving ? "Cerrando…" : "Confirmar castigo"}</button></div>
        </form>
      </section>
    </div>
  );
}

export default WriteOffModal;
