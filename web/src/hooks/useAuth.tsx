import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, ApiError, type AuthState, type AuthUser, type SignInResult } from "@/lib/api";

/** What the sign-in screen must ask for next, when signing in is not finished yet. */
export type PendingSignIn =
  | { step: "email-code"; email: string }
  | { step: "authenticator"; email: string; token: string };

interface AuthContextValue {
  /** false until the first /auth/me answer arrives */
  ready: boolean;
  user: AuthUser | null;
  authRequired: boolean;
  signupEnabled: boolean;
  /** Undefined once signed in; otherwise the next step to show (an emailed code, or the authenticator code). */
  signIn: (email: string, password: string) => Promise<PendingSignIn | undefined>;
  signUp: (name: string, email: string, password: string) => Promise<PendingSignIn | undefined>;
  verifyEmail: (email: string, code: string) => Promise<void>;
  verifyAuthenticator: (token: string, code: string) => Promise<void>;
  /** Re-reads the signed-in user, e.g. after turning two-step sign-in on or off. */
  refreshUser: () => Promise<void>;
  resendCode: (email: string) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  /** Resolves to "signed-in", or "login-required" when an authenticator code is still needed to sign in. */
  resetPassword: (email: string, code: string, newPassword: string) => Promise<"signed-in" | "login-required">;
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

  const settle = useCallback(
    (result: SignInResult): PendingSignIn | undefined => {
      if ("user" in result) {
        adopt(result.user);
        return undefined;
      }
      if ("mfa_required" in result) return { step: "authenticator", email: result.email, token: result.mfa_token };
      return { step: "email-code", email: result.email };
    },
    [adopt],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      ready,
      user: state.user,
      authRequired: state.auth_required,
      signupEnabled: state.signup_enabled,
      signIn: async (email, password) => settle(await api.login(email, password)),
      signUp: async (name, email, password) => settle(await api.signup(name, email, password)),
      verifyEmail: async (email, code) => adopt((await api.verifyEmail(email, code)).user),
      verifyAuthenticator: async (token, code) => adopt((await api.mfaVerify(token, code)).user),
      refreshUser: async () => {
        const next = await api.me();
        setState((s) => ({ ...s, user: next.user }));
      },
      resendCode: async (email) => {
        await api.resendCode(email);
      },
      forgotPassword: async (email) => {
        await api.forgotPassword(email);
      },
      resetPassword: async (email, code, newPassword) => {
        const result = await api.resetPassword(email, code, newPassword);
        if ("user" in result) {
          adopt(result.user);
          return "signed-in";
        }
        return "login-required";
      },
      signOut: async () => {
        await api.logout().catch(() => undefined);
        queryClient.clear();
        setState((s) => ({ ...s, user: null }));
      },
    }),
    [ready, state, adopt, settle, queryClient],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
