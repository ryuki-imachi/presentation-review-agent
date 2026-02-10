import "./Result.css";

interface Props {
  summary: string;
}

export function SummaryCard({ summary }: Props) {
  return (
    <div className="summary-card">
      <h3 className="summary-card__label">総合評価</h3>
      <p className="summary-card__text">{summary}</p>
    </div>
  );
}
