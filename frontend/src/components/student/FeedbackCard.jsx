export default function FeedbackCard({ evaluation, onNext, hasNext, isLast }) {
  const { feedback, covered_points, missed_points, score, max_score } = evaluation;
  const percentage = max_score > 0 ? Math.round((score / max_score) * 100) : 0;
  const isFullScore = score === max_score;

  return (
    <div className={`feedback-card ${isFullScore ? 'feedback-perfect' : 'feedback-partial'}`}>
      <div className="feedback-score-row">
        <div className={`score-badge ${isFullScore ? 'score-perfect' : percentage >= 50 ? 'score-good' : 'score-low'}`}>
          {score} / {max_score}
        </div>
        <div className="score-label">
          {isFullScore ? 'Excellent! Full marks!' :
           percentage >= 50 ? 'Good effort!' : 'Keep practising!'}
        </div>
      </div>

      <p className="feedback-text">{feedback}</p>

      {covered_points && covered_points.length > 0 && (
        <div className="points-section covered-section">
          <h4>Points you covered:</h4>
          <ul className="points-list">
            {covered_points.map((point, i) => (
              <li key={i} className="point-item point-covered">
                <span className="point-icon">✓</span> {point}
              </li>
            ))}
          </ul>
        </div>
      )}

      {missed_points && missed_points.length > 0 && (
        <div className="points-section missed-section">
          <h4>Remember to include next time:</h4>
          <ul className="points-list">
            {missed_points.map((point, i) => (
              <li key={i} className="point-item point-missed">
                <span className="point-icon">→</span> {point}
              </li>
            ))}
          </ul>
        </div>
      )}

      <button className="btn btn-next" onClick={onNext}>
        {isLast ? 'See My Results' : 'Next Question →'}
      </button>
    </div>
  );
}
