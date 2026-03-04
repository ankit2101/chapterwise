import { Navigate, useLocation } from 'react-router-dom';
import { useStudentAuth } from '../../context/StudentAuthContext';

export default function StudentProtectedRoute({ children }) {
  const { student } = useStudentAuth();
  const location = useLocation();

  if (!student) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
