import type { StrengthItem } from "../../types/sse";
import "./Result.css";

interface Props {
  items: StrengthItem[];
}

export function StrengthsList({ items }: Props) {
  return (
    <section className="result-section">
      <h3 className="result-section__title result-section__title--good">良い点</h3>
      <ul className="result-list result-list--good">
        {items.map((s, i) => (
          <li key={i}>
            <strong>{s.category}</strong>: {s.description}
            {s.evidence && <span className="result-evidence">（{s.evidence}）</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
