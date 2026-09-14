import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { SubjectPicker } from "../components/SubjectPicker";

interface Subject { id: string; slug: string; name: string }
interface Topic { id: string; slug: string; name: string }

export function Dashboard() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);

  useEffect(() => {
    api.subjects()
      .then(({ subjects }) => setSubjects(subjects))
      .catch(() => setSubjects([]));
  }, []);

  useEffect(() => {
    if (!selectedSubject) return;
    api.topics(selectedSubject)
      .then(({ topics }) => setTopics(topics))
      .catch(() => setTopics([]));
  }, [selectedSubject]);

  return (
    <div>
      <header className="topbar">
        <span className="wordmark">Feddy Study Coach</span>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <span className="pill">{user?.email}</span>
          <button className="btn-ghost" onClick={signOut}>Sign out</button>
        </div>
      </header>

      <div className="shell" style={{ paddingTop: "3rem" }}>
        <h1 style={{ fontSize: "1.9rem" }}>What are you studying today?</h1>
        <p style={{ marginTop: "0.75rem" }}>Pick a subject, then a topic, to start with the tutor.</p>

        <div style={{ marginTop: "1.5rem" }}>
          <SubjectPicker
            subjects={subjects}
            selectedId={selectedSubject}
            onSelect={setSelectedSubject}
          />
        </div>

        {topics.length > 0 && (
          <>
            <h3 style={{ fontSize: "1rem", marginBottom: "1rem", color: "var(--text-muted)" }}>
              Topics
            </h3>
            <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
              {topics.map((t) => (
                <button
                  key={t.id}
                  className="btn-ghost"
                  onClick={() => navigate(`/tutor?topic=${t.slug}&topicId=${t.id}`)}
                >
                  {t.name}
                </button>
              ))}
            </div>
          </>
        )}

        <button className="btn-primary" onClick={() => navigate("/tutor")}>
          Just start a conversation
        </button>
      </div>
    </div>
  );
}
