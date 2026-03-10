import { useState } from 'react';
import { deleteChapter, regenerateQuestions, renameChapter } from '../../api/adminApi';

function PdfModal({ chapter, onClose }) {
  return (
    <div className="pdf-modal-overlay" onClick={onClose}>
      <div className="pdf-modal" onClick={e => e.stopPropagation()}>
        <div className="pdf-modal-header">
          <span className="pdf-modal-title">{chapter.chapter_name}</span>
          <button className="pdf-modal-close" onClick={onClose} title="Close">×</button>
        </div>
        <iframe
          className="pdf-modal-frame"
          src={`/api/admin/chapter/${chapter.id}/pdf`}
          title={chapter.chapter_name}
        />
      </div>
    </div>
  );
}

export default function ChapterTable({ content, onRefresh }) {
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [loading, setLoading] = useState(null);
  const [pdfChapter, setPdfChapter] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [renameError, setRenameError] = useState('');
  const [renameSaving, setRenameSaving] = useState(false);

  const handleDelete = async (id) => {
    if (confirmDelete !== id) { setConfirmDelete(id); return; }
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

  const startRename = (chapter) => {
    setEditingId(chapter.id);
    setEditingName(chapter.chapter_name);
    setRenameError('');
    setConfirmDelete(null);
  };

  const cancelRename = () => {
    setEditingId(null);
    setEditingName('');
    setRenameError('');
  };

  const saveRename = async (chapter) => {
    const trimmed = editingName.trim();
    if (!trimmed) { setRenameError('Name cannot be empty.'); return; }
    if (trimmed === chapter.chapter_name) { cancelRename(); return; }
    setRenameSaving(true);
    setRenameError('');
    try {
      await renameChapter(chapter.id, trimmed);
      cancelRename();
      onRefresh?.();
    } catch (err) {
      setRenameError(err.message);
    } finally {
      setRenameSaving(false);
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
    <>
      {pdfChapter && <PdfModal chapter={pdfChapter} onClose={() => setPdfChapter(null)} />}

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
                            <td>
                              {editingId === chapter.id ? (
                                <div className="rename-inline">
                                  <input
                                    className="rename-input"
                                    value={editingName}
                                    onChange={e => setEditingName(e.target.value)}
                                    onKeyDown={e => {
                                      if (e.key === 'Enter') saveRename(chapter);
                                      if (e.key === 'Escape') cancelRename();
                                    }}
                                    autoFocus
                                    maxLength={200}
                                  />
                                  <div className="rename-actions">
                                    <button
                                      type="button"
                                      className="btn btn-sm btn-primary"
                                      onClick={() => saveRename(chapter)}
                                      disabled={renameSaving}
                                    >
                                      {renameSaving ? 'Saving…' : 'Save'}
                                    </button>
                                    <button
                                      type="button"
                                      className="btn btn-sm btn-ghost"
                                      onClick={cancelRename}
                                      disabled={renameSaving}
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                  {renameError && <span className="rename-error">{renameError}</span>}
                                </div>
                              ) : (
                                <span className="chapter-name-cell">
                                  <button
                                    type="button"
                                    className="chapter-name-link"
                                    onClick={() => setPdfChapter(chapter)}
                                    title="Click to view PDF"
                                  >
                                    {chapter.chapter_name}
                                  </button>
                                  <button
                                    type="button"
                                    className="rename-btn"
                                    onClick={() => startRename(chapter)}
                                    title="Rename chapter"
                                  >
                                    ✏
                                  </button>
                                </span>
                              )}
                            </td>
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
                                onClick={() => handleDelete(chapter.id)}
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
    </>
  );
}
