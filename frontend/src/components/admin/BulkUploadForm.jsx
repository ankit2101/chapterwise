import { useState, useRef } from 'react';
import { bulkUploadChapters, renameChapter } from '../../api/adminApi';

const BOARDS = ['CBSE', 'ICSE'];
const GRADES = [6, 7, 8, 9, 10];

export default function BulkUploadForm({ onUploadSuccess }) {
  const [board, setBoard] = useState('');
  const [grade, setGrade] = useState('');
  const [subject, setSubject] = useState('');
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [renameError, setRenameError] = useState('');
  const [renameSaving, setRenameSaving] = useState(false);
  const fileInputRef = useRef(null);

  const addFiles = (incoming) => {
    const pdfs = Array.from(incoming).filter(f =>
      f.name.toLowerCase().endsWith('.pdf')
    );
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name));
      return [...prev, ...pdfs.filter(f => !existing.has(f.name))];
    });
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const removeFile = (name) =>
    setFiles(prev => prev.filter(f => f.name !== name));

  const startRename = (r) => {
    setEditingId(r.chapter_id);
    setEditingName(r.chapter_name);
    setRenameError('');
  };

  const cancelRename = () => {
    setEditingId(null);
    setEditingName('');
    setRenameError('');
  };

  const saveRename = async (r) => {
    const trimmed = editingName.trim();
    if (!trimmed) { setRenameError('Name cannot be empty.'); return; }
    if (trimmed === r.chapter_name) { cancelRename(); return; }

    setRenameSaving(true);
    setRenameError('');
    try {
      await renameChapter(r.chapter_id, trimmed);
      setResults(prev => ({
        ...prev,
        results: prev.results.map(row =>
          row.chapter_id === r.chapter_id ? { ...row, chapter_name: trimmed } : row
        ),
      }));
      cancelRename();
      onUploadSuccess?.();
    } catch (err) {
      setRenameError(err.message);
    } finally {
      setRenameSaving(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setResults(null);

    if (!board || !grade || !subject.trim() || files.length === 0) {
      setError('Please fill in all fields and select at least one PDF file.');
      return;
    }

    const formData = new FormData();
    formData.append('board', board);
    formData.append('grade', grade);
    formData.append('subject', subject.trim());
    files.forEach(f => formData.append('pdf_files', f));

    setLoading(true);
    try {
      const data = await bulkUploadChapters(formData);
      setResults(data);
      if (data.success_count > 0) {
        // Keep failed files in the list so the admin can retry / investigate
        const failedNames = new Set(
          (data.results || []).filter(r => !r.success).map(r => r.filename)
        );
        setFiles(prev => prev.filter(f => failedNames.has(f.name)));
        if (fileInputRef.current) fileInputRef.current.value = '';
        onUploadSuccess?.();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-form-card">
      <h2>Bulk Upload Chapters</h2>
      <p className="form-hint" style={{ marginBottom: '1.25rem' }}>
        Upload multiple PDFs at once for the same subject. Chapter names are
        automatically extracted from the first page of each PDF.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      {results && (
        <div className="bulk-results">
          <div className={`alert ${results.success_count > 0 ? 'alert-success' : 'alert-error'}`}>
            <strong>
              {results.success_count} of {results.total} chapter(s) uploaded successfully.
            </strong>
            {results.failure_count > 0 && results.success_count > 0 && (
              <span> {results.failure_count} failed — see details below.</span>
            )}
          </div>

          <table className="bulk-results-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Extracted Chapter Name</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {results.results.map((r, i) => (
                <tr key={i} className={r.success ? 'row-success' : 'row-error'}>
                  <td className="bulk-file-cell" title={r.filename}>{r.filename}</td>
                  <td>
                    {r.success && editingId === r.chapter_id ? (
                      <div className="rename-inline">
                        <input
                          className="rename-input"
                          value={editingName}
                          onChange={e => setEditingName(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') saveRename(r);
                            if (e.key === 'Escape') cancelRename();
                          }}
                          autoFocus
                          maxLength={200}
                        />
                        <div className="rename-actions">
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            onClick={() => saveRename(r)}
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
                    ) : r.chapter_name ? (
                      <span className="chapter-name-cell">
                        {r.chapter_name}
                        {r.success && (
                          <button
                            type="button"
                            className="rename-btn"
                            onClick={() => startRename(r)}
                            title="Rename chapter"
                          >
                            ✏
                          </button>
                        )}
                      </span>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td>
                    {r.success ? (
                      <span className="status-badge status-badge--success">
                        ✓ Uploaded&nbsp;
                        <span className="text-muted">
                          ({r.text_length?.toLocaleString()} chars)
                        </span>
                        {r.warning && (
                          <span className="warning-inline"> ⚠ {r.warning}</span>
                        )}
                      </span>
                    ) : (
                      <span className="status-badge status-badge--error">
                        ✗ {r.error}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={handleSubmit} className="upload-form">
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="bulk-board">Board</label>
            <select
              id="bulk-board"
              value={board}
              onChange={e => setBoard(e.target.value)}
            >
              <option value="">Select Board</option>
              {BOARDS.map(b => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="bulk-grade">Grade</label>
            <select
              id="bulk-grade"
              value={grade}
              onChange={e => setGrade(e.target.value)}
            >
              <option value="">Select Grade</option>
              {GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
            </select>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="bulk-subject">Subject</label>
          <input
            id="bulk-subject"
            type="text"
            value={subject}
            onChange={e => setSubject(e.target.value)}
            placeholder="e.g. Science, Mathematics, English"
            maxLength={100}
          />
        </div>

        {/* Drop Zone */}
        <div
          className={`drop-zone ${isDragging ? 'drop-zone--active' : ''}`}
          onDrop={handleDrop}
          onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            multiple
            style={{ display: 'none' }}
            onChange={e => addFiles(e.target.files)}
          />
          <span className="drop-zone-icon">📂</span>
          <p className="drop-zone-label">
            Drag &amp; drop PDF files here, or <strong>click to browse</strong>
          </p>
          <p className="drop-zone-hint">Multiple PDFs accepted · Max 32 MB each</p>
        </div>

        {/* File List */}
        {files.length > 0 && (
          <div className="bulk-file-list">
            <div className="bulk-file-list-header">
              <span>{files.length} file{files.length !== 1 ? 's' : ''} selected</span>
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                onClick={() => { setFiles([]); if (fileInputRef.current) fileInputRef.current.value = ''; }}
              >
                Clear all
              </button>
            </div>
            {files.map((f, i) => (
              <div key={i} className="bulk-file-item">
                <span className="bulk-file-icon">📄</span>
                <span className="bulk-file-name">{f.name}</span>
                <span className="bulk-file-size">({(f.size / 1024).toFixed(1)} KB)</span>
                <button
                  type="button"
                  className="bulk-file-remove"
                  onClick={() => removeFile(f.name)}
                  title="Remove"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || files.length === 0}
          style={{ marginTop: '0.5rem' }}
        >
          {loading
            ? `Uploading ${files.length} file${files.length !== 1 ? 's' : ''}…`
            : `Upload ${files.length || ''} PDF${files.length !== 1 ? 's' : ''}`}
        </button>
      </form>
    </div>
  );
}
