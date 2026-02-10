import "./Result.css";

interface Props {
  items: string[];
}

export function ImprovementsList({ items }: Props) {
  return (
    <section className="result-section">
      <h3 className="result-section__title result-section__title--improve">改善点</h3>
      <ul className="result-list result-list--improve">
        {items.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
    </section>
  );
}
