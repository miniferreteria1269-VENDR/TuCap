import { useState } from "react";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

function nowLocal() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function ReversalModal({ amount, description, onClose, onConfirm }) {
  const [reason, setReason] = useState("");
  const [reversedAt, setReversedAt] = useState(nowLocal());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    if (reason.trim().length < 3) {
      setError("Explica brevemente por qué se anula este movimiento.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onConfirm({ reason: reason.trim(), reversed_at: new Date(reversedAt).toISOString() });
    } catch (saveError) {
      setError(saveError.message);
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="sheet-modal compact-sheet" role="dialog" aria-modal="true" aria-labelledby="reversal-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading"><div><p className="eyebrow">Corrección auditada</p><h2 id="reversal-title">Anular movimiento</h2></div><button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button></div>
        <form className="client-form" onSubmit={submit}>
          <div className="reversal-target"><div><span>Movimiento original</span><strong>{description}</strong></div><strong>{currency.format(Math.abs(Number(amount)))}</strong></div>
          <p className="warning-note">El registro original no se borrará. TuCap añadirá una contrapartida y conservará el motivo, la fecha y el usuario que hizo la corrección.</p>
          <label className="field full-width"><span>Motivo de la anulación *</span><textarea autoFocus maxLength="500" onChange={(event) => setReason(event.target.value)} placeholder="Ej. Pago registrado dos veces" rows="3" value={reason} /></label>
          <label className="field full-width"><span>Fecha y hora de corrección</span><input onChange={(event) => setReversedAt(event.target.value)} type="datetime-local" value={reversedAt} /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="modal-actions"><button className="cancel-button" type="button" onClick={onClose}>Cancelar</button><button className="danger-button" disabled={saving || reason.trim().length < 3} type="submit">{saving ? "Anulando…" : "Confirmar anulación"}</button></div>
        </form>
      </section>
    </div>
  );
}

export default ReversalModal;
