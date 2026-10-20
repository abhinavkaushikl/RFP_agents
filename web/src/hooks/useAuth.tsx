import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, ApiError, type AuthState, type AuthUser } from "@/lib/api";

interface AuthContextValue {
  /** false until the first /auth/me answer arrives */
  ready: boolean;
  user: AuthUser | null;
  authRequired: boolean;
  signupEnabled: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const INITIAL: AuthState = { user: null, auth_required: false, signup_enabled: true };

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>(INITIAL);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let live = true;
    api
      .me()
      .then((next) => live && setState(next))
      // API unreachable: don't lock the user out of the shell, its connection indicator explains the problem.
      .catch((err) => err instanceof ApiError && console.warn("auth check failed", err.message))
      .finally(() => live && setReady(true));
    return () => {
      live = false;
    };
  }, []);

  const adopt = useCallback(
    (user: AuthUser) => {
      queryClient.clear();
      setState((s) => ({ ...s, user }));
    },
    [queryClient],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      ready,
      user: state.user,
      authRequired: state.auth_required,
      signupEnabled: state.signup_enabled,
      signIn: async (email, password) => adopt((await api.login(email, password)).user),
      signUp: async (name, email, password) => adopt((await api.signup(name, email, password)).user),
      signOut: async () => {
        await api.logout().catch(() => undefined);
        queryClient.clear();
        setState((s) => ({ ...s, user: null }));
      },
    }),
    [ready, state, adopt, queryClient],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
