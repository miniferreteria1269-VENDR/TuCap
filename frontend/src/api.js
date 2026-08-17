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

export function createBorrower(payload) {
  return request("/borrowers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

