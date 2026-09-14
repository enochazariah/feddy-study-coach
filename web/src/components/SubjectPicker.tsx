interface Subject {
  id: string;
  slug: string;
  name: string;
}

export function SubjectPicker({
  subjects,
  selectedId,
  onSelect,
}: {
  subjects: Subject[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
      {subjects.map((s) => (
        <button
          key={s.id}
          className={selectedId === s.id ? "btn-primary" : "btn-ghost"}
          onClick={() => onSelect(s.id)}
        >
          {s.name}
        </button>
      ))}
    </div>
  );
}
