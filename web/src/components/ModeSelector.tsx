const MODES = [
  { id: "beginner", label: "Beginner" },
  { id: "standard", label: "Standard" },
  { id: "deep", label: "Deep" },
  { id: "socratic", label: "Socratic" },
  { id: "practice", label: "Practice" },
] as const;

export function ModeSelector({
  mode,
  onChange,
}: {
  mode: string;
  onChange: (mode: string) => void;
}) {
  return (
    <div style={{ display: "flex", gap: "0.4rem" }}>
      {MODES.map((m) => (
        <button
          key={m.id}
          onClick={() => onChange(m.id)}
          className={mode === m.id ? "btn-primary" : "btn-ghost"}
          style={{ fontSize: "0.85rem", padding: "0.4rem 0.9rem" }}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
