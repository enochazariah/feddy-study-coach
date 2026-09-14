import { useEffect, useRef, useState } from "react";
import { useAuth } from "./AuthContext";

declare global {
  interface Window {
    google?: any;
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

export function GoogleSignInButton() {
  const buttonRef = useRef<HTMLDivElement>(null);
  const { signInWithGoogleIdToken } = useAuth();
  const [signingIn, setSigningIn] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;

    let attempts = 0;
    let retryTimer: number | undefined;
    let disposed = false;

    const renderGoogleButton = () => {
      if (disposed) return;

      if (!window.google || !buttonRef.current) {
        if (attempts++ < 50) {
          retryTimer = window.setTimeout(renderGoogleButton, 100);
        }
        return;
      }

      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,

        callback: async (response: { credential: string }) => {
          setSigningIn(true);
          setError("");

          try {
            await signInWithGoogleIdToken(response.credential);

            // Authentication succeeded — enter the workspace immediately.
          } catch (err) {
            console.error("Google sign-in failed:", err);
            setError("Google sign-in failed. Please try again.");
          } finally {
            setSigningIn(false);
          }
        },
      });

      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: "outline",
        size: "large",
        shape: "pill",
        text: "signin_with",
      });
    };

    renderGoogleButton();

    return () => {
      disposed = true;

      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
      }
    };
  }, [signInWithGoogleIdToken]);

  if (!GOOGLE_CLIENT_ID) return null;

  return (
    <div>
      <div ref={buttonRef} />

      {signingIn && (
        <p className="login-note" aria-live="polite">
          Opening your study workspace...
        </p>
      )}

      {error && (
        <p className="login-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}