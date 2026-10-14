import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getTokens, setTokens, setUnauthorizedHandler } from "./api";
import type { KeyPair } from "@ledgeit/proof-core";
import { ensureSigningKey } from "./keys";
import type { Role, User } from "./types";

interface AuthState {
  user: User | null;
  key: KeyPair | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  can: (...roles: Role[]) => boolean;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [key, setKey] = useState<KeyPair | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    setTokens(null);
    setUser(null);
    setKey(null);
  }, []);

  const bootstrap = useCallback(async () => {
    const me = await api<User>("/auth/me");
    setUser(me);
    try {
      setKey(await ensureSigningKey(me));
    } catch {
      setKey(null); // signing unavailable (e.g. private window); read-only still works
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!getTokens()) {
      setLoading(false);
      return;
    }
    bootstrap().catch(logout).finally(() => setLoading(false));
  }, [bootstrap, logout]);

  const login = useCallback(async (email: string, password: string) => {
    const r = await api<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      json: { email, password },
    });
    setTokens({ access_token: r.access_token, refresh_token: r.refresh_token });
    await bootstrap();
  }, [bootstrap]);

  const can = useCallback((...roles: Role[]) => !!user && roles.includes(user.role), [user]);

  return <Ctx.Provider value={{ user, key, loading, login, logout, can }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
