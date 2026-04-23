import { createContext, useContext, useEffect, useState } from 'react';

const AuthContext = createContext(null);
const SESSION_KEY = 'ai-electricity-advisor.auth';
const SESSION_TTL_MS = 6 * 60 * 60 * 1000;

function clearStoredSession() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(SESSION_KEY);
}

function readStoredSession() {
  if (typeof window === 'undefined') return null;

  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    if (!parsed?.user || !parsed?.expiresAt) {
      clearStoredSession();
      return null;
    }

    if (Date.now() > parsed.expiresAt) {
      clearStoredSession();
      return null;
    }

    return parsed.user;
  } catch {
    clearStoredSession();
    return null;
  }
}

function writeStoredSession(userData) {
  if (typeof window === 'undefined') return;

  window.localStorage.setItem(
    SESSION_KEY,
    JSON.stringify({
      user: userData,
      expiresAt: Date.now() + SESSION_TTL_MS,
    }),
  );
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => readStoredSession());

  useEffect(() => {
    if (!user) {
      clearStoredSession();
      return undefined;
    }

    // Refresh expiry on load and whenever the authenticated user changes.
    writeStoredSession(user);

    const timeoutId = window.setTimeout(() => {
      clearStoredSession();
      setUser(null);
    }, SESSION_TTL_MS);

    return () => window.clearTimeout(timeoutId);
  }, [user]);

  const login = (userData) => {
    writeStoredSession(userData);
    setUser(userData);
  };

  const logout = () => {
    clearStoredSession();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
