// api.js
const BASE_URL = 'http://localhost:8000/api'; // Update if needed

export async function login(email, password) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  return res.json();
}

export async function signup(data) {
  const res = await fetch(`${BASE_URL}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

export async function getUserProfile(token) {
  const res = await fetch(`${BASE_URL}/auth/profile`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return res.json();
}

export async function getPlugins() {
  const res = await fetch(`${BASE_URL}/plugins`);
  return res.json();
}

// Add more endpoints as needed...
