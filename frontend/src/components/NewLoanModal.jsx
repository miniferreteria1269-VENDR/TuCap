import { useMemo, useState } from "react";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

function localToday() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
}

function oneMonthAfter(value) {
  const [year, month, day] = value.split("-").map(Number);
  const target = new Date(Date.UTC(year, month, 1));
  const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(day, lastDay));
  return target.toISOString().slice(0, 10);
}

function NewLoanModal({ client, capitalOnHand, onClose, onSave }) {
  const initialDate = localToday();
  const [form, setForm] = useState({
    original_principal: "",
    monthly_interest_rate: "",
    start_date: initialDate,
    first_interest_date: oneMonthAfter(initialDate),
    collateral_description: "",
    collateral_estimated_value: "",
    notes: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const principal = Number(form.original_principal) || 0;
  const rate = Number(form.monthly_interest_rate) || 0;
  const monthlyInterest = principal * rate / 100;
  const resultingExposure = Number(client.outstanding_principal || 0) + principal;
  const creditLimit = Number(client.credit_limit || 0);
  const exceedsCreditLimit = creditLimit > 0 && resultingExposure > creditLimit;
  const exceedsRecordedCapital = principal > Number(capitalOnHand || 0);

  const update = (field) => (event) => {
    const value = event.target.value;
    setForm((current) => ({ ...current, [field]: value }));
  };

  const changeStartDate = (event) => {
    const value = event.target.value;
    setForm((current) => ({
      ...current,
      start_date: value,
      first_interest_date: value ? oneMonthAfter(value) : "",
    }));
  };

  const payload = useMemo(() => ({
    borrower_id: client.id,
    original_principal: form.original_principal,
    monthly_interest_rate: form.monthly_interest_rate,
    start_date: form.start_date,
    first_interest_date: form.first_interest_date,
    collateral_description: form.collateral_description.trim() || null,
    collateral_estimated_value: form.collateral_estimated_value || null,
    notes: form.notes.trim() || null,
  }), [client.id, form]);

  const submit = async (event) => {
    event.preventDefault();
    if (principal <= 0) {
      setError("El capital prestado debe ser mayor que cero.");
      return;
    }
    if (rate < 0 || form.monthly_interest_rate === "") {
      setError("Ingresa la tasa de interés mensual.");
      return;
    }
    if (!form.start_date || !form.first_interest_date) {
      setError("Selecciona las fechas del préstamo y del primer interés.");
      return;
    }
    if (form.first_interest_date <= form.start_date) {
      setError("La primera fecha de interés debe ser posterior al préstamo.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      await onSave(payload);
    } catch (saveError) {
      setError(saveError.message);
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="sheet-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-loan-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading">
          <div>
            <p className="eyebrow">{client.full_name}</p>
            <h2 id="new-loan-title">Nuevo préstamo</h2>
          </div>
          <button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button>
        </div>

        <form className="client-form" onSubmit={submit}>
          <div className="form-grid">
            <label className="field">
              <span>Capital prestado *</span>
              <div className="money-input">
                <span>$</span>
                <input autoFocus inputMode="decimal" min="0.01" onChange={update("original_principal")} placeholder="0.00" step="0.01" type="number" value={form.original_principal} />
              </div>
            </label>
            <label className="field">
              <span>Interés mensual *</span>
              <div className="suffix-input">
                <input inputMode="decimal" min="0" onChange={update("monthly_interest_rate")} placeholder="0" step="0.01" type="number" value={form.monthly_interest_rate} />
                <span>%</span>
              </div>
            </label>
          </div>

          <div className="interest-preview">
            <span>Interés por mes</span>
            <strong>{currency.format(monthlyInterest)}</strong>
            <small>Calculado sobre el capital pendiente; no se capitaliza.</small>
          </div>

          <div className="form-grid">
            <label className="field">
              <span>Fecha del préstamo</span>
              <input onChange={changeStartDate} type="date" value={form.start_date} />
            </label>
            <label className="field">
              <span>Primer interés</span>
              <input min={form.start_date} onChange={update("first_interest_date")} type="date" value={form.first_interest_date} />
            </label>
          </div>

          <label className="field full-width">
            <span>Garantía</span>
            <textarea onChange={update("collateral_description")} placeholder="Descripción, identificación o condición de la garantía" rows="2" value={form.collateral_description} />
          </label>

          <label className="field full-width">
            <span>Valor estimado de la garantía</span>
            <div className="money-input">
              <span>$</span>
              <input inputMode="decimal" min="0" onChange={update("collateral_estimated_value")} placeholder="0.00" step="0.01" type="number" value={form.collateral_estimated_value} />
            </div>
          </label>

          <label className="field full-width">
            <span>Notas</span>
            <textarea onChange={update("notes")} placeholder="Condiciones, evaluación de riesgo o acuerdos relevantes" rows="3" value={form.notes} />
          </label>

          {exceedsCreditLimit && (
            <p className="warning-note">Este préstamo elevará la exposición a {currency.format(resultingExposure)}, sobre el límite manual de {currency.format(creditLimit)}. Puedes continuar.</p>
          )}
          {exceedsRecordedCapital && (
            <p className="warning-note">El préstamo supera el capital disponible registrado ({currency.format(capitalOnHand || 0)}). Puedes continuar, pero el saldo quedará negativo.</p>
          )}
          <p className="info-note">TuCap registra la tasa indicada; no determina si los términos son legalmente válidos.</p>
          {error && <p className="form-error" role="alert">{error}</p>}

          <div className="modal-actions">
            <button className="cancel-button" type="button" onClick={onClose}>Cancelar</button>
            <button className="primary-button" disabled={saving} type="submit">
              {saving ? "Creando…" : `Prestar ${currency.format(principal)}`}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default NewLoanModal;
