import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { GoogleSignInButton } from "../auth/GoogleSignInButton";
import { useAuth } from "../auth/AuthContext";

export function Landing() {
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) navigate("/demo", { replace: true });
  }, [user, navigate]);

  return (
    <div>
      <header className="topbar">
        <span className="wordmark">Feddy Study Coach</span>
      </header>

      <div className="shell" style={{ paddingTop: "5rem", paddingBottom: "5rem" }}>
        <p className="pill">Adaptive tutoring</p>
        <h1 style={{ fontSize: "2.75rem", marginTop: "1rem", maxWidth: "16ch" }}>
          Understand it. Don't just get the answer.
        </h1>
        <p style={{ fontSize: "1.05rem", marginTop: "1.25rem" }}>
          Feddy Study Coach explains concepts at your level, lets you practice, checks what
          you actually understand, and tells you what to study next — instead of handing
          you a finished answer and moving on.
        </p>

        <button
          className="btn-primary demo-cta"
          onClick={() => navigate("/login")}
          type="button"
        >
          Enter Study Workspace <span aria-hidden="true">&rarr;</span>
        </button>

        <div style={{ marginTop: "2rem" }}>
          <GoogleSignInButton />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "2rem" }}>
          <Feature
            title="Explains at your level"
            body="Beginner, standard, deep, or Socratic — switch modes mid-conversation."
          />
          <Feature
            title="Tracks real progress"
            body="Mastery is built from evidence, not a score the model makes up."
          />
          <Feature
            title="Built to grow with you"
            body="One tutor today; research and practice specialists arrive next."
          />
        </div>
      </div>
    </div>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h3 style={{ fontSize: "1.05rem", marginBottom: "0.5rem" }}>{title}</h3>
      <p style={{ fontSize: "0.92rem" }}>{body}</p>
    </div>
  );
}
