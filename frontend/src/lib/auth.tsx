import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { UNAUTHORIZED_EVENT, api, clearToken, getToken, setToken } from './api';
import type { AuthResponse, Organization, User } from '../types';

interface RegisterInput {
  email: string;
  password: string;
  full_name: string;
  organization_name: string;
}

interface AuthContextValue {
  user: User | null;
  organization: Organization | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
      setOrganization(null);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function hydrate() {
      if (!getToken()) {
        if (!cancelled) setLoading(false);
        return;
      }

      try {
        const [me, org] = await Promise.all([
          api.get<User>('/auth/me'),
          api.get<Organization>('/organizations/current'),
        ]);
        if (!cancelled) {
          setUser(me);
          setOrganization(org);
        }
      } catch {
        if (!cancelled) {
          clearToken();
          setUser(null);
          setOrganization(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void hydrate();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.post<AuthResponse>('/auth/login', { email, password });
    setToken(data.access_token);
    setUser(data.user);
    setOrganization(data.organization);
  }, []);

  const register = useCallback(async (input: RegisterInput) => {
    const data = await api.post<AuthResponse>('/auth/register', input);
    setToken(data.access_token);
    setUser(data.user);
    setOrganization(data.organization);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } finally {
      clearToken();
      setUser(null);
      setOrganization(null);
    }
  }, []);

  const refresh = useCallback(async () => {
    const [me, org] = await Promise.all([
      api.get<User>('/auth/me'),
      api.get<Organization>('/organizations/current'),
    ]);
    setUser(me);
    setOrganization(org);
  }, []);

  return (
    <AuthContext.Provider value={{ user, organization, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
