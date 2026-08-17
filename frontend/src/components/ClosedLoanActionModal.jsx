import { useState } from "react";

import { addCollateralRecovery, updateLoanPerformance } from "../api";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

function today() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
}

function ClosedLoanActionModal({ loan, mode, onClose, onComplete }) {
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const [lateCount, setLateCount] = useState(String(loan.performance?.late_payment_count || 0));
  const [notes, setNotes] = useState(loan.performance?.notes || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const recoveryMode = mode === "recovery";

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const detail = recoveryMode
        ? await addCollateralRecovery(loan.id, { amount, occurred_at: `${date}T12:00:00Z`, notes: notes.trim() || null })
        : await updateLoanPerformance(loan.id, { late_payment_count: Number(lateCount) || 0, notes: notes.trim() || null });
      onComplete(detail);
    } catch (saveError) {
      setError(saveError.message);
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="sheet-modal compact-sheet" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading"><div><p className="eyebrow">Préstamo cerrado</p><h2>{recoveryMode ? "Registrar recuperación" : "Editar desempeño"}</h2></div><button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button></div>
        <form className="client-form" onSubmit={submit}>
          {recoveryMode && <><div className="withdrawal-balance"><span>Recuperado hasta ahora</span><strong>{currency.format(loan.performance?.collateral_recovered || 0)}</strong></div><label className="field full-width"><span>Cantidad recuperada *</span><div className="money-input prominent-input"><span>$</span><input autoFocus inputMode="decimal" min="0.01" onChange={(event) => setAmount(event.target.value)} placeholder="0.00" step="0.01" type="number" value={amount} /></div></label><label className="field full-width"><span>Fecha</span><input onChange={(event) => setDate(event.target.value)} type="date" value={date} /></label></>}
          {!recoveryMode && <label className="field full-width"><span>Cantidad de pagos tardíos</span><input autoFocus inputMode="numeric" min="0" onChange={(event) => setLateCount(event.target.value)} step="1" type="number" value={lateCount} /></label>}
          <label className="field full-width"><span>Notas</span><textarea onChange={(event) => setNotes(event.target.value)} rows="2" value={notes} /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="modal-actions"><button className="cancel-button" type="button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={saving || (recoveryMode && Number(amount) <= 0)} type="submit">{saving ? "Guardando…" : "Guardar"}</button></div>
        </form>
      </section>
    </div>
  );
}

export default ClosedLoanActionModal;
