import { useState } from "react";

const emptyForm = {
  full_name: "",
  phone: "",
  email: "",
  government_id: "",
  address: "",
  credit_limit: "",
  notes: "",
  status: "active",
};

const statusOptions = [
  { value: "active", label: "Activo", detail: "Puede recibir préstamos nuevos." },
  { value: "inactive", label: "Inactivo", detail: "Pausa nuevos préstamos sin borrar su historial." },
  { value: "blocked", label: "Bloqueado", detail: "Marca al cliente como no elegible para nuevos préstamos." },
];

function formFromClient(client) {
  if (!client) return emptyForm;
  return {
    full_name: client.full_name || "",
    phone: client.phone || "",
    email: client.email || "",
    government_id: client.government_id || "",
    address: client.address || "",
    credit_limit: client.credit_limit || "",
    notes: client.notes || "",
    status: client.status || "active",
  };
}

function ClientFormModal({ client = null, onClose, onSave }) {
  const editing = Boolean(client);
  const [form, setForm] = useState(() => formFromClient(client));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const update = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.full_name.trim()) {
      setError("El nombre del cliente es obligatorio.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      await onSave({
        full_name: form.full_name.trim(),
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        government_id: form.government_id.trim() || null,
        address: form.address.trim() || null,
        notes: form.notes.trim() || null,
        credit_limit: form.credit_limit || "0.00",
        ...(editing ? { status: form.status } : {}),
      });
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
        aria-labelledby="client-form-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading">
          <div>
            <p className="eyebrow">{editing ? "Perfil del cliente" : "Personas"}</p>
            <h2 id="client-form-title">{editing ? "Editar cliente" : "Nuevo cliente"}</h2>
          </div>
          <button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button>
        </div>

        <form className="client-form" onSubmit={handleSubmit}>
          <label className="field full-width">
            <span>Nombre completo *</span>
            <input
              autoFocus
              maxLength="180"
              onChange={update("full_name")}
              placeholder="Ej. María López"
              value={form.full_name}
            />
          </label>

          {editing && (
            <fieldset className="borrower-status-field">
              <legend>Estado del cliente</legend>
              <div className="borrower-status-options">
                {statusOptions.map((option) => (
                  <label className={`borrower-status-option ${form.status === option.value ? "selected" : ""}`} key={option.value}>
                    <input checked={form.status === option.value} name="borrower-status" onChange={update("status")} type="radio" value={option.value} />
                    <span><strong>{option.label}</strong><small>{option.detail}</small></span>
                  </label>
                ))}
              </div>
              <small>Los pagos y el cierre de préstamos existentes seguirán disponibles.</small>
            </fieldset>
          )}

          <div className="form-grid">
            <label className="field">
              <span>Teléfono</span>
              <input inputMode="tel" onChange={update("phone")} placeholder="0000-0000" value={form.phone} />
            </label>
            <label className="field">
              <span>DUI / Identificación</span>
              <input onChange={update("government_id")} placeholder="Opcional" value={form.government_id} />
            </label>
          </div>

          <label className="field full-width">
            <span>Correo electrónico</span>
            <input inputMode="email" onChange={update("email")} placeholder="Opcional" value={form.email} />
          </label>

          <label className="field full-width">
            <span>Dirección</span>
            <textarea onChange={update("address")} placeholder="Dirección de residencia o referencia" rows="2" value={form.address} />
          </label>

          <label className="field full-width">
            <span>Límite de crédito</span>
            <div className="money-input">
              <span>$</span>
              <input
                inputMode="decimal"
                min="0"
                onChange={update("credit_limit")}
                placeholder="0.00"
                step="0.01"
                type="number"
                value={form.credit_limit}
              />
            </div>
            <small>Referencia manual; no autoriza préstamos automáticamente.</small>
          </label>

          <label className="field full-width">
            <span>Notas</span>
            <textarea onChange={update("notes")} placeholder="Referencias, contexto o evaluación personal" rows="3" value={form.notes} />
          </label>

          {error && <p className="form-error" role="alert">{error}</p>}

          <div className="modal-actions">
            <button className="cancel-button" type="button" onClick={onClose}>Cancelar</button>
            <button className="primary-button" disabled={saving} type="submit">
              {saving ? "Guardando…" : editing ? "Guardar cambios" : "Guardar cliente"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default ClientFormModal;
