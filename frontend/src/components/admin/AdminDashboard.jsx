import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAdminAuth } from '../../context/AdminAuthContext';
import { getContent } from '../../api/adminApi';
import UploadForm from './UploadForm';
import BulkUploadForm from './BulkUploadForm';
import Logo from '../shared/Logo';
import ChapterTable from './ChapterTable';
import StudentManagement from './StudentManagement';
import StudentProgress from './StudentProgress';
import LoadingOverlay from '../shared/LoadingOverlay';

export default function AdminDashboard() {
  const [content, setContent] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [uploadMode, setUploadMode] = useState('single'); // 'single' | 'bulk'
  const { username, logout } = useAdminAuth();
  const navigate = useNavigate();

  const loadContent = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getContent();
      setContent(data.content || {});
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadContent();
  }, [loadContent]);

  const handleLogout = async () => {
    await logout();
    navigate('/admin/login');
  };

  const totalChapters = Object.values(content).reduce((sum, grades) =>
    sum + Object.values(grades).reduce((s2, subjects) =>
      s2 + Object.values(subjects).reduce((s3, chapters) => s3 + chapters.length, 0), 0), 0);

  return (
    <div className="admin-layout">
      <header className="admin-header">
        <div className="admin-header-left">
          <Logo size="sm" className="admin-logo-img" />
          <h1>Admin Panel</h1>
        </div>
        <div className="admin-header-right">
          <span className="admin-user">Logged in as <strong>{username}</strong></span>
          <button className="btn btn-sm btn-outline" onClick={() => navigate('/admin/settings')}>
            Settings
          </button>
          <button className="btn btn-sm btn-ghost" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <main className="admin-main">
        <div className="admin-stats-bar">
          <div className="stat-item">
            <span className="stat-value">{totalChapters}</span>
            <span className="stat-label">Chapters Uploaded</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{Object.keys(content).length}</span>
            <span className="stat-label">Boards</span>
          </div>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        {/* Upload mode toggle */}
        <div className="upload-tabs">
          <button
            className={`upload-tab-btn ${uploadMode === 'single' ? 'upload-tab-btn--active' : ''}`}
            onClick={() => setUploadMode('single')}
          >
            Single Upload
          </button>
          <button
            className={`upload-tab-btn ${uploadMode === 'bulk' ? 'upload-tab-btn--active' : ''}`}
            onClick={() => setUploadMode('bulk')}
          >
            Bulk Upload
          </button>
        </div>

        {uploadMode === 'single'
          ? <UploadForm onUploadSuccess={loadContent} />
          : <BulkUploadForm onUploadSuccess={loadContent} />
        }

        <div className="content-section">
          <div className="section-header">
            <h2>Uploaded Content</h2>
            <button className="btn btn-sm btn-outline" onClick={loadContent} disabled={loading}>
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>
          {loading
            ? <LoadingOverlay message="Loading content..." />
            : <ChapterTable content={content} onRefresh={loadContent} />}
        </div>

        <div className="content-section">
          <StudentManagement />
        </div>

        <div className="content-section" style={{ marginTop: '1.5rem' }}>
          <StudentProgress />
        </div>
      </main>
    </div>
  );
}
