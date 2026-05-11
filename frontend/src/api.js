import axios from 'axios';

const root = (process.env.REACT_APP_API_URL || 'http://127.0.0.1:5001').replace(/\/$/, '');

export const api = axios.create({
  baseURL: `${root}/api/`,
});

const TOKEN_KEY = 'expense_tracker_token';

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function persistToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function setAuthToken(token) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}
