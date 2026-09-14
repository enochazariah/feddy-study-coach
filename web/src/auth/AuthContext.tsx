import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type AppUser } from "../api/client";

interface AuthState {
  user: AppUser | null;
  loading: boolean;
  continueWithGmail: (email: string) => Promise<void>;
  signInWithGoogleIdToken: (idToken: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AppUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("feddy_session_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(({ user }) => setUser(user))
      .catch(() => {
        localStorage.removeItem("feddy_session_token");
        localStorage.removeItem("feddy_demo_user");
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const signInWithGoogleIdToken = useCallback(async (idToken: string) => {
    const { token, user } = await api.signInWithGoogle(idToken);
    localStorage.setItem("feddy_session_token", token);
    setUser(user);
  }, []);

  const continueWithGmail = useCallback(async (email: string) => {
    const { token, user } = await api.demoLogin(email);
    localStorage.setItem("feddy_session_token", token);
    localStorage.setItem("feddy_demo_user", JSON.stringify(user));
    setUser(user);
  }, []);

  function signOut() {
    localStorage.removeItem("feddy_session_token");
    localStorage.removeItem("feddy_demo_user");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, continueWithGmail, signInWithGoogleIdToken, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
