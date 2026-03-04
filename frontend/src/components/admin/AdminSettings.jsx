import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAdminAuth } from '../../context/AdminAuthContext';
import { changePassword, saveApiKey, getApiKeyStatus } from '../../api/adminApi';
import Logo from '../shared/Logo';

export default function AdminSettings() {
  const navigate = useNavigate();
  const { username, logout } = useAdminAuth();

  // Password change state
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwLoading, setPwLoading] = useState(false);
  const [pwMessage, setPwMessage] = useState(null);

  // API key state
  const [apiKey, setApiKey] = useState('');
  const [apiKeyStatus, setApiKeyStatus] = useState(null);
  const [apiKeyLoading, setApiKeyLoading] = useState(false);
  const [apiKeyMessage, setApiKeyMessage] = useState(null);

  useEffect(() => {
    getApiKeyStatus()
      .then(setApiKeyStatus)
      .catch(() => {});
  }, []);

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setPwMessage(null);
    if (!currentPw || !newPw || !confirmPw) {
      setPwMessage({ type: 'error', text: 'Please fill in all password fields.' });
      return;
    }
    setPwLoading(true);
    try {
      const data = await changePassword(currentPw, newPw, confirmPw);
      setPwMessage({ type: 'success', text: data.message || 'Password changed successfully.' });
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
    } catch (err) {
      setPwMessage({ type: 'error', text: err.message });
    } finally {
      setPwLoading(false);
    }
  };

  const handleSaveApiKey = async (e) => {
    e.preventDefault();
    setApiKeyMessage(null);
    if (!apiKey.trim()) {
      setApiKeyMessage({ type: 'error', text: 'Please enter your Anthropic API key.' });
      return;
    }
    setApiKeyLoading(true);
    try {
      const data = await saveApiKey(apiKey.trim());
      setApiKeyMessage({ type: 'success', text: data.message || 'API key saved successfully.' });
      setApiKey('');
      const status = await getApiKeyStatus();
      setApiKeyStatus(status);
    } catch (err) {
      setApiKeyMessage({ type: 'error', text: err.message });
    } finally {
      setApiKeyLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/admin/login');
  };

  return (
    <div className="admin-layout">
      <header className="admin-header">
        <div className="admin-header-left">
          <Logo size="sm" className="admin-logo-img" />
          <h1>Admin Panel</h1>
        </div>
        <div className="admin-header-right">
          <span className="admin-user">Logged in as <strong>{username}</strong></span>
          <button className="btn btn-sm btn-outline" onClick={() => navigate('/admin/dashboard')}>
            Dashboard
          </button>
          <button className="btn btn-sm btn-ghost" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <main className="admin-main settings-main">
        <h2 className="settings-title">Settings</h2>

        {/* API Key Section */}
        <div className="settings-card">
          <h3>Anthropic API Key</h3>
          <p className="settings-description">
            Required for generating questions and evaluating answers. Get your key from{' '}
            <a href="https://console.anthropic.com" target="_blank" rel="noreferrer">
              console.anthropic.com
            </a>.
          </p>

          {apiKeyStatus && (
            <div className={`api-key-status ${apiKeyStatus.configured ? 'status-ok' : 'status-missing'}`}>
              {apiKeyStatus.configured
                ? `API key is configured (source: ${apiKeyStatus.source === 'admin_panel' ? 'Admin Panel' : 'Environment Variable'})`
                : 'No API key configured. Tests cannot run until a key is added.'}
            </div>
          )}

          {apiKeyMessage && (
            <div className={`alert alert-${apiKeyMessage.type}`}>{apiKeyMessage.text}</div>
          )}

          <form onSubmit={handleSaveApiKey} className="settings-form">
            <div className="form-group">
              <label htmlFor="api-key-input">Enter New API Key</label>
              <input
                id="api-key-input"
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="sk-ant-..."
                autoComplete="off"
              />
              <span className="form-hint">The key is stored securely in the database and never displayed again.</span>
            </div>
            <button type="submit" className="btn btn-primary" disabled={apiKeyLoading}>
              {apiKeyLoading ? 'Saving...' : 'Save API Key'}
            </button>
          </form>
        </div>

        {/* Password Section */}
        <div className="settings-card">
          <h3>Change Password</h3>

          {pwMessage && (
            <div className={`alert alert-${pwMessage.type}`}>{pwMessage.text}</div>
          )}

          <form onSubmit={handlePasswordChange} className="settings-form">
            <div className="form-group">
              <label htmlFor="current-pw">Current Password</label>
              <input
                id="current-pw"
                type="password"
                value={currentPw}
                onChange={e => setCurrentPw(e.target.value)}
                placeholder="Enter current password"
                autoComplete="current-password"
              />
            </div>
            <div className="form-group">
              <label htmlFor="new-pw">New Password</label>
              <input
                id="new-pw"
                type="password"
                value={newPw}
                onChange={e => setNewPw(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label htmlFor="confirm-pw">Confirm New Password</label>
              <input
                id="confirm-pw"
                type="password"
                value={confirmPw}
                onChange={e => setConfirmPw(e.target.value)}
                placeholder="Repeat new password"
                autoComplete="new-password"
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={pwLoading}>
              {pwLoading ? 'Changing...' : 'Change Password'}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
