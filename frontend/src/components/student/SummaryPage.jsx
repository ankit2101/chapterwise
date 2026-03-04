import { useNavigate } from 'react-router-dom';
import Logo from '../shared/Logo';

export default function SummaryPage({ summary, chapterName, subject, grade, board }) {
  const navigate = useNavigate();
  const { total_questions, total_score, max_score, percentage, questions_detail, missed_topics, sections } = summary;

  const grade_label = percentage >= 80 ? 'Excellent!' :
                      percentage >= 60 ? 'Good work!' :
                      percentage >= 40 ? 'Keep practising!' : 'More practice needed!';

  const grade_color = percentage >= 80 ? 'grade-excellent' :
                      percentage >= 60 ? 'grade-good' :
                      percentage >= 40 ? 'grade-ok' : 'grade-low';

  return (
    <div className="summary-page">
      <header className="site-header">
        <div className="header-inner">
          <Logo size="md" />
        </div>
      </header>

      <main className="summary-main">
        <div className="summary-hero">
          <h1>Test Complete!</h1>
          <p className="summary-chapter">
            {board} &middot; Grade {grade} &middot; {subject}
          </p>
          <p className="summary-chapter-name">{chapterName}</p>
        </div>

        <div className="summary-score-card">
          <div className={`big-score ${grade_color}`}>
            <span className="score-number">{total_score}</span>
            <span className="score-separator">/</span>
            <span className="score-total">{max_score}</span>
          </div>
          <div className="score-percentage">{percentage}%</div>
          <div className={`score-label ${grade_color}`}>{grade_label}</div>
        </div>

        {sections && sections.length > 0 && (
          <div className="summary-sections">
            <h3>Section-wise Score</h3>
            <div className="sections-table">
              {sections.map((sec, i) => {
                const secPct = sec.possible > 0 ? Math.round((sec.earned / sec.possible) * 100) : 0;
                const sectionLabel = sec.marks === 1 ? 'Section A (1 Mark)' :
                                     sec.marks === 3 ? 'Section B (3 Marks)' : 'Section C (5 Marks)';
                return (
                  <div key={i} className="section-row">
                    <span className={`section-label marks-badge-${sec.marks}`}>{sectionLabel}</span>
                    <span className="section-count">{sec.count} Q</span>
                    <span className="section-score">{sec.earned}/{sec.possible}</span>
                    <span className={`section-pct ${secPct >= 80 ? 'grade-excellent' : secPct >= 50 ? 'grade-good' : 'grade-low'}`}>
                      {secPct}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {missed_topics && missed_topics.length > 0 && (
          <div className="summary-missed-topics">
            <h3>Topics to review:</h3>
            <div className="topic-chips">
              {missed_topics.map((topic, i) => (
                <span key={i} className="topic-chip">{topic}</span>
              ))}
            </div>
          </div>
        )}

        <div className="summary-breakdown">
          <h3>Question-by-Question Breakdown</h3>
          {questions_detail.map((q, i) => {
            const qPct = q.max_score > 0 ? Math.round((q.score / q.max_score) * 100) : 0;
            return (
              <div key={i} className={`breakdown-item ${q.score === q.max_score ? 'breakdown-perfect' : 'breakdown-partial'}`}>
                <div className="breakdown-header">
                  <span className="breakdown-q-num">Q{q.question_number}</span>
                  {q.marks && <span className={`marks-badge marks-badge-${q.marks} breakdown-marks`}>{q.marks}M</span>}
                  <span className="breakdown-topic">{q.topic_tag}</span>
                  <span className={`breakdown-score ${qPct >= 80 ? 'score-ok' : 'score-partial'}`}>
                    {q.score}/{q.max_score}
                  </span>
                </div>
                <p className="breakdown-question">{q.question_text}</p>
                {q.missed_points && q.missed_points.length > 0 && (
                  <div className="breakdown-missed">
                    <strong>Missed:</strong> {q.missed_points.join(' • ')}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="summary-actions">
          <button className="btn btn-start" onClick={() => navigate('/')}>
            Practice Another Chapter
          </button>
        </div>
      </main>
    </div>
  );
}
