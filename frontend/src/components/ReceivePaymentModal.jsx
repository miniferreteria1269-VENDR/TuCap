import { useEffect, useMemo, useState } from "react";

import { getPaymentPreview, recordPayment } from "../api";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

function localToday() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
}

function rounded(value) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

function inputAmount(value) {
  return value === 0 ? "0" : String(rounded(value));
}

function ReceivePaymentModal({ client, loan, onClose, onComplete }) {
  const [receivedDate, setReceivedDate] = useState(localToday());
  const [amountReceived, setAmountReceived] = useState("");
  const [toInterest, setToInterest] = useState("0");
  const [toPrincipal, setToPrincipal] = useState("0");
  const [notes, setNotes] = useState("");
  const [balances, setBalances] = useState({
    accrued_interest: loan.accrued_interest,
    principal_outstanding: loan.principal_outstanding,
  });
  const [loadingPreview, setLoadingPreview] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState(null);

  const interestDue = Number(balances.accrued_interest || 0);
  const principalDue = Number(balances.principal_outstanding || 0);
  const received = Number(amountReceived) || 0;
  const interestAllocation = Number(toInterest) || 0;
  const principalAllocation = Number(toPrincipal) || 0;
  const allocated = rounded(interestAllocation + principalAllocation);
  const remaining = rounded(received - allocated);
  const totalDue = rounded(interestDue + principalDue);

  const allocationError = useMemo(() => {
    if (received <= 0) return "Ingresa la cantidad recibida.";
    if (received > totalDue) return "El pago excede el saldo total del préstamo.";
    if (interestAllocation > interestDue) return "El abono a interés no puede superar el interés acumulado.";
    if (principalAllocation > principalDue) return "El abono a capital no puede superar el capital pendiente.";
    if (remaining !== 0) {
      return remaining > 0
        ? `Falta distribuir ${currency.format(remaining)}.`
        : `La distribución excede lo recibido por ${currency.format(Math.abs(remaining))}.`;
    }
    return "";
  }, [interestAllocation, interestDue, principalAllocation, principalDue, received, remaining, totalDue]);

  const applySuggestion = (amount, currentBalances) => {
    const interest = Math.min(amount, Number(currentBalances.accrued_interest || 0));
    const principal = Math.min(
      Math.max(amount - interest, 0),
      Number(currentBalances.principal_outstanding || 0),
    );
    setToInterest(inputAmount(interest));
    setToPrincipal(inputAmount(principal));
  };

  useEffect(() => {
    let cancelled = false;
    getPaymentPreview(loan.id, 0, receivedDate)
      .then((preview) => {
        if (!cancelled) setBalances(preview);
      })
      .catch((previewError) => {
        if (!cancelled) setError(previewError.message);
      })
      .finally(() => {
        if (!cancelled) setLoadingPreview(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loan.id, receivedDate]);

  const changeAmount = (event) => {
    const value = event.target.value;
    setAmountReceived(value);
    applySuggestion(Number(value) || 0, balances);
    setError("");
  };

  const changeDate = (event) => {
    setReceivedDate(event.target.value);
    setAmountReceived("");
    setToInterest("0");
    setToPrincipal("0");
    setLoadingPreview(true);
    setError("");
  };

  const submit = async (event) => {
    event.preventDefault();
    if (allocationError) {
      setError(allocationError);
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await recordPayment(loan.id, {
        amount_received: inputAmount(received),
        amount_to_interest: inputAmount(interestAllocation),
        amount_to_principal: inputAmount(principalAllocation),
        received_at: `${receivedDate}T12:00:00Z`,
        notes: notes.trim() || null,
      });
      setReceipt(result);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  };

  if (receipt) {
    const paidOff = receipt.loan.status === "paid";
    return (
      <div className="modal-backdrop" role="presentation">
        <section className="sheet-modal compact-sheet payment-receipt" role="dialog" aria-modal="true" aria-labelledby="payment-result-title">
          <div className="receipt-check" aria-hidden="true">✓</div>
          <p className="eyebrow">Pago registrado</p>
          <h2 id="payment-result-title">{currency.format(receipt.payment.amount_received)}</h2>
          <p className="receipt-client">{client.full_name}</p>

          <div className="receipt-allocation">
            <div><span>A interés</span><strong>{currency.format(receipt.payment.amount_to_interest)}</strong></div>
            <div><span>A capital</span><strong>{currency.format(receipt.payment.amount_to_principal)}</strong></div>
          </div>

          <div className="recalculated-balance">
            <p className="eyebrow">Saldo recalculado</p>
            <div><span>Interés pendiente</span><strong>{currency.format(receipt.loan.accrued_interest)}</strong></div>
            <div><span>Capital pendiente</span><strong>{currency.format(receipt.loan.principal_outstanding)}</strong></div>
          </div>

          {paidOff && <p className="paid-off-message">Préstamo pagado en su totalidad.</p>}
          <button className="primary-button full-action" type="button" onClick={() => onComplete(receipt)}>Listo</button>
        </section>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="sheet-modal" role="dialog" aria-modal="true" aria-labelledby="receive-payment-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading">
          <div>
            <p className="eyebrow">{client.full_name}</p>
            <h2 id="receive-payment-title">Recibir pago</h2>
          </div>
          <button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button>
        </div>

        <form className="client-form" onSubmit={submit}>
          <label className="field full-width">
            <span>Fecha del pago</span>
            <input onChange={changeDate} type="date" value={receivedDate} />
          </label>

          <div className="payment-balances" aria-busy={loadingPreview}>
            <article><span>Interés acumulado</span><strong>{loadingPreview ? "…" : currency.format(interestDue)}</strong></article>
            <article><span>Capital pendiente</span><strong>{loadingPreview ? "…" : currency.format(principalDue)}</strong></article>
          </div>

          <label className="field full-width">
            <span>Cantidad recibida *</span>
            <div className="money-input prominent-input">
              <span>$</span>
              <input autoFocus inputMode="decimal" min="0.01" onChange={changeAmount} placeholder="0.00" step="0.01" type="number" value={amountReceived} />
            </div>
          </label>

          <div className="form-grid">
            <label className="field">
              <span>A interés</span>
              <div className="money-input">
                <span>$</span>
                <input inputMode="decimal" max={interestDue} min="0" onChange={(event) => setToInterest(event.target.value)} step="0.01" type="number" value={toInterest} />
              </div>
              <small>Máximo {currency.format(interestDue)}</small>
            </label>
            <label className="field">
              <span>A capital</span>
              <div className="money-input">
                <span>$</span>
                <input inputMode="decimal" max={principalDue} min="0" onChange={(event) => setToPrincipal(event.target.value)} step="0.01" type="number" value={toPrincipal} />
              </div>
              <small>Máximo {currency.format(principalDue)}</small>
            </label>
          </div>

          <div className={remaining === 0 && received > 0 ? "allocation-status complete" : "allocation-status"}>
            <span>{remaining === 0 && received > 0 ? "Distribución completa" : "Pendiente de distribuir"}</span>
            <strong>{currency.format(Math.abs(remaining))}</strong>
          </div>

          {received > 0 && allocationError && <p className="inline-allocation-error">{allocationError}</p>}

          <label className="field full-width">
            <span>Notas</span>
            <textarea onChange={(event) => setNotes(event.target.value)} placeholder="Aviso previo, acuerdo o referencia del pago" rows="2" value={notes} />
          </label>

          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="modal-actions">
            <button className="cancel-button" type="button" onClick={onClose}>Cancelar</button>
            <button className="primary-button" disabled={saving || loadingPreview || Boolean(allocationError)} type="submit">
              {saving ? "Registrando…" : "Confirmar pago"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default ReceivePaymentModal;
