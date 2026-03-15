import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AdminAuthProvider } from './context/AdminAuthContext';
import { StudentAuthProvider } from './context/StudentAuthContext';
import ProtectedRoute from './components/shared/ProtectedRoute';
import StudentProtectedRoute from './components/shared/StudentProtectedRoute';
import ToastContainer from './components/shared/Toast';

import StudentLogin from './components/student/StudentLogin';
import SelectionPage from './components/student/SelectionPage';
import TestPage from './components/student/TestPage';
import CustomTestBuilder from './components/student/CustomTestBuilder';
import AdminLogin from './components/admin/AdminLogin';
import AdminDashboard from './components/admin/AdminDashboard';
import AdminSettings from './components/admin/AdminSettings';

export default function App() {
  return (
    <AdminAuthProvider>
      <StudentAuthProvider>
        <BrowserRouter>
          <ToastContainer />
          <Routes>
            {/* Student login */}
            <Route path="/login" element={<StudentLogin />} />

            {/* Student routes — require login */}
            <Route
              path="/"
              element={
                <StudentProtectedRoute>
                  <SelectionPage />
                </StudentProtectedRoute>
              }
            />
            <Route
              path="/test/:sessionKey"
              element={
                <StudentProtectedRoute>
                  <TestPage />
                </StudentProtectedRoute>
              }
            />
            <Route
              path="/custom-test-builder"
              element={
                <StudentProtectedRoute>
                  <CustomTestBuilder />
                </StudentProtectedRoute>
              }
            />

            {/* Admin routes */}
            <Route path="/admin/login" element={<AdminLogin />} />
            <Route
              path="/admin/dashboard"
              element={
                <ProtectedRoute>
                  <AdminDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/settings"
              element={
                <ProtectedRoute>
                  <AdminSettings />
                </ProtectedRoute>
              }
            />
            <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </StudentAuthProvider>
    </AdminAuthProvider>
  );
}
