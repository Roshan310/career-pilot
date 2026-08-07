"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { getMe, logout as apiLogout } from "@/lib/api/auth";
import { ApiError, tokenStore } from "@/lib/api/client";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  /** Set when the session could not be verified for a reason other than expiry. */
  error: string | null;
  setUser: (u: User | null) => void;
  refreshUser: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshUser = useCallback(async () => {
    if (!tokenStore.isAuthenticated) {
      setUser(null);
      setError(null);
      setLoading(false);
      return;
    }
    setError(null);
    try {
      const me = await getMe();
      setUser(me);
    } catch (err) {
      setUser(null);
      // A dropped connection used to be indistinguishable from an expired
      // session, so a brief outage silently bounced the user to /login. Only an
      // auth failure clears the token; anything else is reported and retryable.
      if (!(err instanceof ApiError) || err.status === 401 || err.status === 403) {
        setError(null);
      } else {
        setError(
          err instanceof ApiError && err.status >= 500
            ? "We couldn't reach CareerPilot. The service may be temporarily down."
            : "We couldn't verify your session. Check your connection and try again.",
        );
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const logout = useCallback(() => {
    apiLogout();
    setUser(null);
    setError(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, error, setUser, refreshUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
