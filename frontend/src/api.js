const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
const TENANT_ID =
  import.meta.env.VITE_TENANT_ID || "00000000-0000-0000-0000-000000000001";

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-ID": TENANT_ID,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "No se pudo completar la solicitud.");
  }

  return response.json();
}

export function getBorrowers() {
  return request("/borrowers");
}

export function getBorrower(borrowerId) {
  return request(`/borrowers/${borrowerId}`);
}

export function createBorrower(payload) {
  return request("/borrowers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCapitalSummary() {
  return request("/capital/summary");
}

export function addCapital(payload) {
  return request("/capital/deposits", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getLoans(borrowerId) {
  const query = borrowerId ? `?borrower_id=${encodeURIComponent(borrowerId)}` : "";
  return request(`/loans${query}`);
}

export function createLoan(payload) {
  return request("/loans", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
