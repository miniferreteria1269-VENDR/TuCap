import { useState } from "react";

function today() {
  return new Date().toISOString().slice(0, 10);
}

function AddCapitalModal({ onClose, onSave }) {
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    if (Number(amount) <= 0) {
      setError("Ingresa una cantidad mayor que cero.");
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
      <section
        className="sheet-modal compact-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-capital-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading">
          <div>
            <p className="eyebrow">Caja de préstamos</p>
            <h2 id="add-capital-title">Agregar capital</h2>
          </div>
          <button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button>
        </div>

        <form className="client-form" onSubmit={submit}>
          <label className="field full-width">
            <span>Cantidad *</span>
            <div className="money-input prominent-input">
              <span>$</span>
              <input
                autoFocus
                inputMode="decimal"
                min="0.01"
                onChange={(event) => setAmount(event.target.value)}
                placeholder="0.00"
                step="0.01"
                type="number"
                value={amount}
              />
            </div>
          </label>

          <label className="field full-width">
            <span>Fecha</span>
            <input onChange={(event) => setDate(event.target.value)} type="date" value={date} />
          </label>

          <label className="field full-width">
            <span>Notas</span>
            <textarea
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Ej. Capital inicial"
              rows="2"
              value={notes}
            />
          </label>

          <p className="info-note">Este movimiento aumenta el capital disponible para préstamos.</p>
          {error && <p className="form-error" role="alert">{error}</p>}

          <div className="modal-actions">
            <button className="cancel-button" type="button" onClick={onClose}>Cancelar</button>
            <button className="primary-button" disabled={saving} type="submit">
              {saving ? "Guardando…" : "Confirmar capital"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default AddCapitalModal;

