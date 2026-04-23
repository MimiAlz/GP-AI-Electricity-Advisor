const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function apiCall(method, path, payload = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (payload) options.body = JSON.stringify(payload);

  const res = await fetch(`${BASE_URL}${path}`, options);
  const data = await res.json().catch(() => ({ detail: 'Non-JSON response' }));

  if (!res.ok) {
    const err = new Error(data.detail || `Request failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const authApi = {
  login: (identifier, password) =>
    apiCall('POST', '/auth/login', { identifier, password }),
  signup: (national_id, username, password) =>
    apiCall('POST', '/auth/signup', { national_id, username, password }),
  deleteAccount: (national_id) =>
    apiCall('DELETE', `/users/${national_id}`),
};

export const houseApi = {
  list: async (nationalId) => {
    const data = await apiCall('GET', `/users/${nationalId}/houses`);
    return Array.isArray(data?.houses) ? data.houses : [];
  },
  create: (nationalId, house_id, address) =>
    apiCall('POST', `/users/${nationalId}/houses`, { house_id, address }),
  get: (nationalId, houseId) =>
    apiCall('GET', `/users/${nationalId}/houses/${houseId}`),
  update: (nationalId, houseId, address) =>
    apiCall('PUT', `/users/${nationalId}/houses/${houseId}`, { address }),
  remove: (nationalId, houseId) =>
    apiCall('DELETE', `/users/${nationalId}/houses/${houseId}`),
};

export const forecastApi = {
  list: (nationalId, houseId) =>
    apiCall('GET', `/users/${nationalId}/houses/${houseId}/forecasts`),
  get: (nationalId, houseId, forecastId) =>
    apiCall('GET', `/users/${nationalId}/houses/${houseId}/forecasts/${forecastId}`),
  create: (nationalId, houseId, forecast_month) =>
    apiCall('POST', `/users/${nationalId}/houses/${houseId}/forecasts`, { forecast_month }),
};

export const healthApi = {
  hello: () => fetch(`${BASE_URL}/hello`).then((r) => r.text()),
};
