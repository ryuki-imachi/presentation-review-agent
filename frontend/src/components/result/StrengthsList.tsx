import "./Result.css";

interface Props {
  items: string[];
}

export function StrengthsList({ items }: Props) {
  return (
    <section className="result-section">
      <h3 className="result-section__title result-section__title--good">良い点</h3>
      <ul className="result-list result-list--good">
        {items.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
    </section>
  );
}
