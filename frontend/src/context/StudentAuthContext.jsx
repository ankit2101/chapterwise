import { createContext, useContext, useState, useCallback } from 'react';

const StudentAuthContext = createContext(null);

const STORAGE_KEY = 'cw_student';

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function StudentAuthProvider({ children }) {
  const [student, setStudent] = useState(() => loadFromStorage());

  const login = useCallback((studentData) => {
    const s = { id: studentData.student_id, name: studentData.name };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    setStudent(s);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setStudent(null);
  }, []);

  return (
    <StudentAuthContext.Provider value={{ student, login, logout }}>
      {children}
    </StudentAuthContext.Provider>
  );
}

export function useStudentAuth() {
  return useContext(StudentAuthContext);
}
