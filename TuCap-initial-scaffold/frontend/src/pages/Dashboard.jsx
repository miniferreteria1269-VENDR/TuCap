import MetricCard from "../components/MetricCard";

function Dashboard() {
  return (
    <>
      <section className="hero-card">
        <p className="eyebrow">Capital disponible</p>
        <h2>$0.00</h2>
        <p className="hero-detail">Listo para registrar el capital inicial</p>
        <button className="secondary-button" type="button">Agregar capital</button>
      </section>

      <section className="metric-grid" aria-label="Resumen de cartera">
        <MetricCard label="Por cobrar" value="$0.00" detail="Capital pendiente" />
        <MetricCard label="Interés acumulado" value="$0.00" detail="Pendiente de cobro" tone="accent" />
        <MetricCard label="Préstamos activos" value="0" detail="0 clientes" />
        <MetricCard label="Cobrado este mes" value="$0.00" detail="Interés + capital" />
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Actividad</p>
            <h3>Próximos cobros</h3>
          </div>
          <button className="text-button" type="button">Ver todos</button>
        </div>
        <div className="empty-state">
          <span className="empty-icon" aria-hidden="true">✓</span>
          <strong>Todo al día</strong>
          <p>Los próximos cobros aparecerán aquí.</p>
        </div>
      </section>
    </>
  );
}

export default Dashboard;

