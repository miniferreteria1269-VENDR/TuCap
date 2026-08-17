import { useEffect, useMemo, useState } from "react";

import { createBorrower, getBorrowers } from "../api";
import ClientFormModal from "../components/ClientFormModal";

const money = new Intl.NumberFormat("es-SV", {
  style: "currency",
  currency: "USD",
});

function initials(name) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function ClientsPage() {
  const [clients, setClients] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [selected, setSelected] = useState(null);

  const loadClients = async () => {
    setLoading(true);
    setLoadError("");
    try {
      setClients(await getBorrowers());
    } catch (error) {
      setLoadError(error.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    getBorrowers()
      .then((result) => {
        if (!cancelled) setClients(result);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredClients = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("es");
    if (!normalized) return clients;
    return clients.filter((client) =>
      [client.full_name, client.phone, client.government_id]
        .filter(Boolean)
        .some((value) => value.toLocaleLowerCase("es").includes(normalized)),
    );
  }, [clients, query]);

  const saveClient = async (payload) => {
    const created = await createBorrower(payload);
    setShowForm(false);
    await loadClients();
    setSelected({
      ...created,
      active_loan_count: 0,
      outstanding_principal: "0.00",
      accrued_interest: "0.00",
    });
  };

  if (selected) {
    return (
      <section className="client-detail">
        <button className="back-button" type="button" onClick={() => setSelected(null)}>← Clientes</button>
        <div className="client-identity-card">
          <span className="client-avatar large">{initials(selected.full_name)}</span>
          <div>
            <p className="eyebrow">Cliente</p>
            <h2>{selected.full_name}</h2>
            <p>{selected.phone || "Sin teléfono registrado"}</p>
          </div>
        </div>

        <div className="detail-metrics">
          <article>
            <span>Capital pendiente</span>
            <strong>{money.format(selected.outstanding_principal || 0)}</strong>
          </article>
          <article>
            <span>Interés acumulado</span>
            <strong>{money.format(selected.accrued_interest || 0)}</strong>
          </article>
          <article>
            <span>Límite de crédito</span>
            <strong>{money.format(selected.credit_limit || 0)}</strong>
          </article>
        </div>

        <button className="primary-button full-action" type="button">Crear nuevo préstamo</button>

        <section className="detail-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Información</p>
              <h3>Datos del cliente</h3>
            </div>
          </div>
          <dl className="contact-list">
            <div><dt>Teléfono</dt><dd>{selected.phone || "—"}</dd></div>
            <div><dt>Correo</dt><dd>{selected.email || "—"}</dd></div>
            <div><dt>Identificación</dt><dd>{selected.government_id || "—"}</dd></div>
            <div><dt>Dirección</dt><dd>{selected.address || "—"}</dd></div>
            <div><dt>Notas</dt><dd>{selected.notes || "—"}</dd></div>
          </dl>
        </section>

        <section className="detail-section">
          <p className="eyebrow">Cartera</p>
          <h3>Préstamos</h3>
          <div className="empty-state compact">
            <strong>Sin préstamos registrados</strong>
            <p>Los préstamos de este cliente aparecerán aquí.</p>
          </div>
        </section>
      </section>
    );
  }

  return (
    <section className="clients-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Personas</p>
          <h2>Clientes</h2>
          <p>{clients.length} registrados</p>
        </div>
        <button className="primary-button small-action" type="button" onClick={() => setShowForm(true)}>+ Nuevo</button>
      </div>

      <label className="search-box">
        <span aria-hidden="true">⌕</span>
        <input
          aria-label="Buscar clientes"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar por nombre, teléfono o DUI"
          value={query}
        />
        {query && <button type="button" onClick={() => setQuery("")} aria-label="Limpiar búsqueda">×</button>}
      </label>

      {loading && <div className="list-message">Cargando clientes…</div>}
      {loadError && (
        <div className="list-message error-message">
          <strong>No pudimos cargar los clientes.</strong>
          <p>{loadError}</p>
          <button className="text-button" type="button" onClick={loadClients}>Intentar de nuevo</button>
        </div>
      )}

      {!loading && !loadError && filteredClients.length === 0 && (
        <div className="list-message">
          <span className="empty-icon" aria-hidden="true">♙</span>
          <strong>{query ? "No encontramos coincidencias" : "Agrega tu primer cliente"}</strong>
          <p>{query ? "Prueba con otro nombre, teléfono o DUI." : "Los datos personales y límites de crédito se administran aquí."}</p>
          {!query && <button className="primary-button" type="button" onClick={() => setShowForm(true)}>Nuevo cliente</button>}
        </div>
      )}

      {!loading && !loadError && filteredClients.length > 0 && (
        <div className="client-list">
          {filteredClients.map((client) => (
            <button className="client-row" key={client.id} type="button" onClick={() => setSelected(client)}>
              <span className="client-avatar">{initials(client.full_name)}</span>
              <span className="client-main">
                <strong>{client.full_name}</strong>
                <small>{client.phone || "Sin teléfono"}</small>
              </span>
              <span className="client-balance">
                <strong>{money.format(client.outstanding_principal || 0)}</strong>
                <small>{client.active_loan_count || 0} activos</small>
              </span>
              <span className="row-chevron" aria-hidden="true">›</span>
            </button>
          ))}
        </div>
      )}

      {showForm && <ClientFormModal onClose={() => setShowForm(false)} onSave={saveClient} />}
    </section>
  );
}

export default ClientsPage;
