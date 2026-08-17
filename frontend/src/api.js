const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
const TOKEN_KEY = "tucap_access_token";

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  const { authenticated = true, ...fetchOptions } = options;
  const token = getAccessToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      ...(authenticated && token ? { Authorization: `Bearer ${token}` } : {}),
      ...fetchOptions.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (response.status === 401 && authenticated) {
      clearAccessToken();
      window.dispatchEvent(new Event("tucap:unauthorized"));
    }
    throw new Error(body?.detail || "No se pudo completar la solicitud.");
  }

  return response.json();
}

export function login(email, password) {
  return request("/auth/login", {
    method: "POST",
    authenticated: false,
    body: JSON.stringify({ email, password }),
  });
}

export function getCurrentUser() {
  return request("/auth/me");
}

export function acceptDisclaimer() {
  return request("/auth/accept-disclaimer", {
    method: "POST",
    body: JSON.stringify({ accepted: true }),
  });
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

export function getPaymentPreview(loanId, amountReceived, asOf) {
  const query = new URLSearchParams({
    amount_received: String(amountReceived),
    as_of: asOf,
  });
  return request(`/loans/${loanId}/payment-preview?${query.toString()}`);
}

export function recordPayment(loanId, payload) {
  return request(`/loans/${loanId}/payments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
