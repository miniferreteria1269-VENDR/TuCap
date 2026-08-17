import { useState } from "react";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

function today() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
}

function WithdrawCapitalModal({ available, onClose, onSave }) {
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const numericAmount = Number(amount) || 0;
  const resultingBalance = Number(available) - numericAmount;

  const submit = async (event) => {
    event.preventDefault();
    if (numericAmount <= 0) {
      setError("Ingresa una cantidad mayor que cero.");
      return;
    }
    if (numericAmount > Number(available)) {
      setError("El retiro no puede superar el capital disponible.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onSave({
        amount,
        occurred_at: `${date}T12:00:00Z`,
        notes: notes.trim() || null,
      });
    } catch (saveError) {
      setError(saveError.message);
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="sheet-modal compact-sheet" role="dialog" aria-modal="true" aria-labelledby="withdraw-capital-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading">
          <div><p className="eyebrow">Caja de préstamos</p><h2 id="withdraw-capital-title">Retirar capital</h2></div>
          <button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button>
        </div>

        <form className="client-form" onSubmit={submit}>
          <div className="withdrawal-balance"><span>Disponible ahora</span><strong>{currency.format(available)}</strong></div>
          <label className="field full-width">
            <span>Cantidad a retirar *</span>
            <div className="money-input prominent-input"><span>$</span><input autoFocus inputMode="decimal" max={available} min="0.01" onChange={(event) => setAmount(event.target.value)} placeholder="0.00" step="0.01" type="number" value={amount} /></div>
          </label>
          <div className={resultingBalance < 0 ? "withdrawal-result invalid" : "withdrawal-result"}><span>Capital restante</span><strong>{currency.format(resultingBalance)}</strong></div>
          <label className="field full-width"><span>Fecha</span><input onChange={(event) => setDate(event.target.value)} type="date" value={date} /></label>
          <label className="field full-width"><span>Motivo o notas</span><textarea onChange={(event) => setNotes(event.target.value)} placeholder="Ej. Retiro para uso personal" rows="2" value={notes} /></label>
          <p className="info-note">El retiro reduce el capital disponible, pero no modifica los saldos de los préstamos.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="modal-actions">
            <button className="cancel-button" type="button" onClick={onClose}>Cancelar</button>
            <button className="primary-button" disabled={saving || numericAmount <= 0 || numericAmount > Number(available)} type="submit">{saving ? "Registrando…" : "Confirmar retiro"}</button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default WithdrawCapitalModal;
