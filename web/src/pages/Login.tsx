import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { GoogleSignInButton } from "../auth/GoogleSignInButton";
import { useAuth } from "../auth/AuthContext";
import "../styles/login.css";

export function Login() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const destination = "/demo";

  useEffect(() => {
    if (user) {
      navigate(destination, { replace: true });
    }
  }, [destination, navigate, user]);

  return (
    <main className="login-screen">
      <section className="login-card" aria-labelledby="login-title">
        <p className="login-eyebrow">Feddy Study Coach</p>

        <h1 id="login-title">Your study space starts here.</h1>

        <p className="login-copy">
          Sign in with Google to access your materials, questions, and learning progress.
        </p>

        <GoogleSignInButton />
      </section>
    </main>
  );
}