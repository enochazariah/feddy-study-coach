import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { PdfHub } from "../components/PdfHub";
import { ResearchHub } from "../components/ResearchHub";
import { ActiveLearningHub } from "../components/ActiveLearningHub";
import { TutorChat } from "./TutorChat";
import "../styles/demo-workspace.css";

type Hub = "chat" | "documents" | "research" | "recall";

export function DemoWorkspace() {
  const [activeHub, setActiveHub] = useState<Hub>("chat");
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  function handleSignOut() {
    signOut();
    navigate("/login", { replace: true });
  }

  return (
    <main className="demo-workspace">
      <header className="workspace-nav">
        <div><p className="workspace-nav__eyebrow">Feddy workspace</p><h1>Study with intent.</h1><span className="workspace-user">{user?.email}</span></div>
        <nav aria-label="Study hubs">
          {([ ["chat", "Tutor Chat"], ["documents", "PDF Hub"], ["research", "Research & Video"], ["recall", "Active Recall"] ] as const).map(([id, label]) => <button key={id} className={`workspace-tab${activeHub === id ? " workspace-tab--active" : ""}`} onClick={() => setActiveHub(id)}>{label}</button>)}
          <button className="workspace-signout" onClick={handleSignOut}>Sign out</button>
        </nav>
      </header>
      <section className="workspace-content">
        {activeHub === "chat" && <TutorChat />}
        {activeHub === "documents" && <PdfHub />}
        {activeHub === "research" && <ResearchHub />}
        {activeHub === "recall" && <ActiveLearningHub />}
      </section>
    </main>
  );
}

export default DemoWorkspace;
