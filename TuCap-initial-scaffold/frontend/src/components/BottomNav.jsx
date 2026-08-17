const items = [
  { id: "dashboard", label: "Inicio", icon: "⌂" },
  { id: "borrowers", label: "Clientes", icon: "♙" },
  { id: "loans", label: "Préstamos", icon: "$" },
  { id: "more", label: "Más", icon: "•••" },
];

function BottomNav({ active, onChange }) {
  return (
    <nav className="bottom-nav" aria-label="Navegación principal">
      {items.map((item) => (
        <button
          className={active === item.id ? "nav-item active" : "nav-item"}
          key={item.id}
          onClick={() => onChange(item.id)}
          type="button"
        >
          <span className="nav-icon" aria-hidden="true">{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

export default BottomNav;

