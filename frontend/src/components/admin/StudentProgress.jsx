import { useState, useEffect, useCallback } from 'react';
import { getStudentProgress } from '../../api/adminApi';

function formatDuration(seconds) {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function ScoreBadge({ percentage }) {
  if (percentage == null) return <span className="badge badge-muted">—</span>;
  const cls = percentage >= 70 ? 'badge-ok' : percentage >= 40 ? 'badge-warning' : 'badge-fail';
  return <span className={`badge ${cls}`}>{percentage}%</span>;
}

function StatusBadge({ status }) {
  const map = {
    completed: 'badge-ok',
    active: 'badge-active',
    expired: 'badge-muted',
  };
  return <span className={`badge ${map[status] || 'badge-muted'}`}>{status}</span>;
}

function DetailModal({ session, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card progress-detail-modal" onClick={e => e.stopPropagation()}>
        <div className="progress-detail-header">
          <div>
            <h3>{session.student_name}</h3>
            <p className="progress-detail-meta">
              {session.board} · Grade {session.grade} · {session.subject} · {session.chapter_name}
            </p>
          </div>
          <button className="btn btn-sm btn-ghost modal-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="progress-detail-summary">
          <div className="progress-stat">
            <span className="progress-stat-value">
              {session.total_score}/{session.max_score}
            </span>
            <span className="progress-stat-label">Score</span>
          </div>
          <div className="progress-stat">
            <span className="progress-stat-value">
              <ScoreBadge percentage={session.percentage} />
            </span>
            <span className="progress-stat-label">Percentage</span>
          </div>
          <div className="progress-stat">
            <span className="progress-stat-value">{formatDuration(session.duration_seconds)}</span>
            <span className="progress-stat-label">Time Taken</span>
          </div>
          <div className="progress-stat">
            <span className="progress-stat-value">
              {session.questions_answered}/{session.total_questions}
            </span>
            <span className="progress-stat-label">Questions</span>
          </div>
        </div>

        <div className="progress-questions-list">
          {session.answers.length === 0 ? (
            <p className="empty-state" style={{ padding: '1rem 0' }}>No answers recorded.</p>
          ) : (
            session.answers.map((a, i) => (
              <div key={i} className="progress-question-item">
                <div className="progress-q-header">
                  <span className="progress-q-num">Q{a.question_number}</span>
                  <span className="progress-q-topic">{a.topic_tag}</span>
                  <span className="progress-q-score">{a.score}/{a.max_score} marks</span>
                </div>
                <p className="progress-q-text">{a.question_text}</p>
                <div className="progress-q-answer">
                  <strong>Student's answer:</strong> {a.student_answer || '—'}
                </div>
                {a.feedback && (
                  <div className="progress-q-feedback">{a.feedback}</div>
                )}
                {a.missed_points?.length > 0 && (
                  <div className="progress-q-missed">
                    <strong>Missed:</strong> {a.missed_points.join('; ')}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

const PAGE_SIZE = 10;

export default function StudentProgress() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getStudentProgress();
      setSessions(data.sessions || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = sessions.filter(s => {
    const matchSearch =
      !search ||
      s.student_name.toLowerCase().includes(search.toLowerCase()) ||
      s.chapter_name.toLowerCase().includes(search.toLowerCase()) ||
      s.subject.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === 'all' || s.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageRows = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  // Reset to page 1 when filters change
  const handleSearch = (val) => { setSearch(val); setPage(1); };
  const handleStatus = (val) => { setStatusFilter(val); setPage(1); };

  return (
    <div className="student-progress-section">
      <div className="section-header">
        <h2>Student Progress</h2>
        <button className="btn btn-sm btn-outline" onClick={load} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <div className="progress-filters">
        <input
          type="text"
          className="progress-search"
          placeholder="Search by student, chapter or subject..."
          value={search}
          onChange={e => handleSearch(e.target.value)}
        />
        <select
          className="progress-status-filter"
          value={statusFilter}
          onChange={e => handleStatus(e.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="completed">Completed</option>
          <option value="active">Active</option>
          <option value="expired">Expired</option>
        </select>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {!loading && filtered.length === 0 ? (
        <p className="empty-state">
          {sessions.length === 0 ? 'No test attempts yet.' : 'No results match your filters.'}
        </p>
      ) : (
        <>
          <div className="table-wrap">
            <table className="chapter-table progress-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Chapter</th>
                  <th>Grade / Board</th>
                  <th>Questions</th>
                  <th>Score</th>
                  <th>Time Taken</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map(s => (
                  <tr key={s.session_key}>
                    <td><strong>{s.student_name}</strong></td>
                    <td>
                      <div className="chapter-name-cell">{s.chapter_name}</div>
                      <div className="text-muted">{s.subject}</div>
                    </td>
                    <td>Grade {s.grade} · {s.board}</td>
                    <td>{s.questions_answered}/{s.total_questions}</td>
                    <td>
                      <div>{s.max_score > 0 ? `${s.total_score}/${s.max_score}` : '—'}</div>
                      <ScoreBadge percentage={s.percentage} />
                    </td>
                    <td>{formatDuration(s.duration_seconds)}</td>
                    <td className="text-muted">{s.started_at}</td>
                    <td><StatusBadge status={s.status} /></td>
                    <td>
                      {s.answers.length > 0 && (
                        <button
                          className="btn btn-xs btn-outline"
                          onClick={() => setSelected(s)}
                        >
                          View
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="progress-pagination">
              <button
                className="btn btn-xs btn-outline"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                ← Prev
              </button>
              <span className="pagination-info">
                Page {currentPage} of {totalPages} · {filtered.length} results
              </span>
              <button
                className="btn btn-xs btn-outline"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}

      {selected && (
        <DetailModal session={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
