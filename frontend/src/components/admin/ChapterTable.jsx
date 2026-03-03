import { useState } from 'react';
import { deleteChapter, regenerateQuestions } from '../../api/adminApi';

export default function ChapterTable({ content, onRefresh }) {
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [loading, setLoading] = useState(null);

  const handleDelete = async (id, name) => {
    if (confirmDelete !== id) {
      setConfirmDelete(id);
      return;
    }
    setLoading(`delete-${id}`);
    try {
      await deleteChapter(id);
      onRefresh?.();
    } catch (err) {
      alert(`Could not delete: ${err.message}`);
    } finally {
      setLoading(null);
      setConfirmDelete(null);
    }
  };

  const handleRegenerate = async (id) => {
    setLoading(`regen-${id}`);
    try {
      await regenerateQuestions(id);
      onRefresh?.();
      alert('Questions cache cleared. New questions will be generated on the next test.');
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  const boards = Object.keys(content).sort();
  if (boards.length === 0) {
    return (
      <div className="empty-state">
        <p>No chapters uploaded yet. Upload a PDF to get started.</p>
      </div>
    );
  }

  return (
    <div className="chapter-table-container">
      {boards.map(board => (
        <div key={board} className="board-section">
          <h3 className="board-heading">{board}</h3>
          {Object.keys(content[board]).sort((a, b) => Number(a) - Number(b)).map(grade => (
            <div key={grade} className="grade-section">
              <h4 className="grade-heading">Grade {grade}</h4>
              {Object.keys(content[board][grade]).sort().map(subject => (
                <div key={subject} className="subject-section">
                  <h5 className="subject-heading">{subject}</h5>
                  <table className="chapter-table">
                    <thead>
                      <tr>
                        <th>Chapter</th>
                        <th>Text Size</th>
                        <th>Questions</th>
                        <th>Uploaded</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {content[board][grade][subject].map(chapter => (
                        <tr key={chapter.id}>
                          <td className="chapter-name-cell">{chapter.chapter_name}</td>
                          <td className="text-center">
                            <span className={chapter.text_length < 300 ? 'badge badge-warning' : 'badge badge-ok'}>
                              {chapter.text_length.toLocaleString()} chars
                            </span>
                          </td>
                          <td className="text-center">
                            {chapter.has_questions_cache
                              ? <span className="badge badge-ok">Cached</span>
                              : <span className="badge badge-muted">Not cached</span>}
                          </td>
                          <td className="text-center text-muted">{chapter.created_at}</td>
                          <td className="actions-cell">
                            <button
                              className="btn btn-sm btn-outline"
                              onClick={() => handleRegenerate(chapter.id)}
                              disabled={loading === `regen-${chapter.id}`}
                              title="Clear question cache to regenerate questions on next test"
                            >
                              {loading === `regen-${chapter.id}` ? '...' : 'Refresh Q'}
                            </button>
                            <button
                              className={`btn btn-sm ${confirmDelete === chapter.id ? 'btn-danger' : 'btn-delete'}`}
                              onClick={() => handleDelete(chapter.id, chapter.chapter_name)}
                              disabled={loading === `delete-${chapter.id}`}
                              onBlur={() => {
                                if (confirmDelete === chapter.id) setTimeout(() => setConfirmDelete(null), 200);
                              }}
                            >
                              {loading === `delete-${chapter.id}` ? '...' :
                               confirmDelete === chapter.id ? 'Confirm Delete' : 'Delete'}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
