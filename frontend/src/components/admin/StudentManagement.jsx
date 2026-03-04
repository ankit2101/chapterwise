import { useState, useEffect, useCallback } from 'react';
import { getStudents, createStudent, deleteStudent, resetStudentPin } from '../../api/adminApi';

export default function StudentManagement() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);

  // Create form state
  const [newName, setNewName] = useState('');
  const [newPin, setNewPin] = useState('');
  const [creating, setCreating] = useState(false);

  // Reset PIN state
  const [resetId, setResetId] = useState(null);
  const [resetPin, setResetPin] = useState('');
  const [resetting, setResetting] = useState(false);

  const loadStudents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getStudents();
      setStudents(data.students || []);
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStudents(); }, [loadStudents]);

  const showMsg = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 4000);
  };

  const handleCreate = async () => {
    const name = newName.trim();
    const pin = newPin.trim();
    if (!name) { showMsg('error', 'Name is required.'); return; }
    if (!/^\d{4}$/.test(pin)) { showMsg('error', 'PIN must be exactly 4 digits.'); return; }
    setCreating(true);
    try {
      await createStudent(name, pin);
      showMsg('success', `Student "${name}" created with PIN ${pin}.`);
      setNewName('');
      setNewPin('');
      loadStudents();
    } catch (err) {
      showMsg('error', err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete student "${name}"? Their test history will also be removed.`)) return;
    try {
      await deleteStudent(id);
      showMsg('success', `Student "${name}" deleted.`);
      loadStudents();
    } catch (err) {
      showMsg('error', err.message);
    }
  };

  const handleResetPin = async () => {
    const pin = resetPin.trim();
    if (!/^\d{4}$/.test(pin)) { showMsg('error', 'PIN must be exactly 4 digits.'); return; }
    setResetting(true);
    try {
      const data = await resetStudentPin(resetId, pin);
      showMsg('success', data.message);
      setResetId(null);
      setResetPin('');
    } catch (err) {
      showMsg('error', err.message);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="student-mgmt-section">
      <div className="section-header">
        <h2>Student Accounts</h2>
        <button className="btn btn-sm btn-outline" onClick={loadStudents} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {message && (
        <div className={`alert alert-${message.type}`}>{message.text}</div>
      )}

      {/* Create student form */}
      <div className="settings-card">
        <h3>Add New Student</h3>
        <div className="student-create-form">
          <div className="form-group">
            <label htmlFor="new-student-name">Student Name</label>
            <input
              id="new-student-name"
              type="text"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              placeholder="e.g. Priya Sharma"
              maxLength={100}
              autoComplete="off"
            />
          </div>
          <div className="form-group">
            <label htmlFor="new-student-pin">4-Digit PIN</label>
            <input
              id="new-student-pin"
              type="text"
              maxLength={4}
              value={newPin}
              onChange={e => setNewPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              placeholder="e.g. 1234"
              autoComplete="off"
            />
          </div>
          <button type="button" className="btn btn-primary" onClick={handleCreate} disabled={creating}>
            {creating ? 'Creating...' : 'Add Student'}
          </button>
        </div>
      </div>

      {/* Reset PIN modal */}
      {resetId !== null && (
        <div className="modal-overlay" onClick={() => { setResetId(null); setResetPin(''); }}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <h3>Reset PIN</h3>
            <p>Enter a new 4-digit PIN for <strong>{students.find(s => s.id === resetId)?.name}</strong>.</p>
            <div className="settings-form">
              <div className="form-group">
                <label htmlFor="reset-pin-input">New PIN</label>
                <input
                  id="reset-pin-input"
                  type="text"
                  maxLength={4}
                  value={resetPin}
                  onChange={e => setResetPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
                  onKeyDown={e => e.key === 'Enter' && handleResetPin()}
                  placeholder="e.g. 1234"
                  autoComplete="off"
                  autoFocus
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-primary" onClick={handleResetPin} disabled={resetting}>
                  {resetting ? 'Saving...' : 'Save PIN'}
                </button>
                <button type="button" className="btn btn-outline" onClick={() => { setResetId(null); setResetPin(''); }}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Student table */}
      {students.length === 0 && !loading ? (
        <p className="empty-state">No students yet. Add one above.</p>
      ) : (
        <div className="table-wrap">
          <table className="chapter-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Added</th>
                <th>Active Tests</th>
                <th>Completed</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {students.map(s => (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.created_at}</td>
                  <td>{s.active_sessions}</td>
                  <td>{s.completed_sessions}</td>
                  <td>
                    <div className="action-btns">
                      <button
                        className="btn btn-xs btn-outline"
                        onClick={() => { setResetId(s.id); setResetPin(''); }}
                      >
                        Reset PIN
                      </button>
                      <button
                        className="btn btn-xs btn-danger"
                        onClick={() => handleDelete(s.id, s.name)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
