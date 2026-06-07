import type { ImprovementItem } from "../../types/sse";
import "./Result.css";

interface Props {
  items: ImprovementItem[];
}

export function ImprovementsList({ items }: Props) {
  return (
    <section className="result-section">
      <h3 className="result-section__title result-section__title--improve">改善点</h3>
      <ul className="result-list result-list--improve">
        {items.map((s, i) => (
          <li key={i}>
            <span className={`result-priority result-priority--${s.priority}`}>
              {s.priority}
            </span>
            <strong>{s.category}</strong>: {s.issue}
            {s.suggestion && <p className="result-suggestion">→ {s.suggestion}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
