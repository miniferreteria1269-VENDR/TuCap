const pageCopy = {
  borrowers: {
    eyebrow: "Personas",
    title: "Clientes",
    text: "Aquí administraremos información de contacto, límite de crédito, notas y comportamiento histórico.",
    action: "Nuevo cliente",
  },
  loans: {
    eyebrow: "Cartera",
    title: "Préstamos",
    text: "Aquí vivirán los préstamos activos, sus saldos, intereses acumulados, garantías y pagos.",
    action: "Nuevo préstamo",
  },
  more: {
    eyebrow: "TuCap",
    title: "Más opciones",
    text: "Movimientos de capital, retiros, reportes, configuración y avisos legales.",
    action: "Configuración",
  },
};

function PlaceholderPage({ page }) {
  const copy = pageCopy[page];
  return (
    <section className="section-block page-intro">
      <p className="eyebrow">{copy.eyebrow}</p>
      <h2>{copy.title}</h2>
      <p>{copy.text}</p>
      <button className="primary-button" type="button">{copy.action}</button>
    </section>
  );
}

export default PlaceholderPage;

