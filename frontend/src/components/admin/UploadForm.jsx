import { useState, useRef } from 'react';
import { uploadChapter } from '../../api/adminApi';

const BOARDS = ['CBSE', 'ICSE'];
const GRADES = [6, 7, 8, 9, 10];

export default function UploadForm({ onUploadSuccess }) {
  const [board, setBoard] = useState('');
  const [grade, setGrade] = useState('');
  const [subject, setSubject] = useState('');
  const [chapterName, setChapterName] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setResult(null);

    if (!board || !grade || !subject.trim() || !chapterName.trim() || !file) {
      setError('Please fill in all fields and select a PDF file.');
      return;
    }

    const formData = new FormData();
    formData.append('board', board);
    formData.append('grade', grade);
    formData.append('subject', subject.trim());
    formData.append('chapter_name', chapterName.trim());
    formData.append('pdf_file', file);

    setLoading(true);
    try {
      const data = await uploadChapter(formData);
      setResult(data);
      // Reset form
      setBoard('');
      setGrade('');
      setSubject('');
      setChapterName('');
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      onUploadSuccess?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-form-card">
      <h2>Upload Chapter PDF</h2>

      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <div className="alert alert-success">
          <strong>Uploaded successfully!</strong> &quot;{result.chapter_name}&quot; —{' '}
          {result.text_length.toLocaleString()} characters extracted.
          {result.warning && (
            <div className="alert-warning-inline"> {result.warning}</div>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="upload-form">
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="upload-board">Board</label>
            <select id="upload-board" value={board} onChange={e => setBoard(e.target.value)}>
              <option value="">Select Board</option>
              {BOARDS.map(b => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="upload-grade">Grade</label>
            <select id="upload-grade" value={grade} onChange={e => setGrade(e.target.value)}>
              <option value="">Select Grade</option>
              {GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
            </select>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="upload-subject">Subject</label>
          <input
            id="upload-subject"
            type="text"
            value={subject}
            onChange={e => setSubject(e.target.value)}
            placeholder="e.g. Science, Mathematics, English"
            maxLength={100}
          />
        </div>

        <div className="form-group">
          <label htmlFor="upload-chapter">Chapter Name</label>
          <input
            id="upload-chapter"
            type="text"
            value={chapterName}
            onChange={e => setChapterName(e.target.value)}
            placeholder="e.g. Chapter 1: Food – Where Does It Come From?"
            maxLength={200}
          />
        </div>

        <div className="form-group">
          <label htmlFor="upload-file">Chapter PDF</label>
          <input
            id="upload-file"
            type="file"
            accept=".pdf"
            ref={fileInputRef}
            onChange={e => setFile(e.target.files[0] || null)}
          />
          {file && (
            <span className="file-info">
              {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </span>
          )}
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Uploading and Extracting...' : 'Upload PDF'}
        </button>
      </form>
    </div>
  );
}
