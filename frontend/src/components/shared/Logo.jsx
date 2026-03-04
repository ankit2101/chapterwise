import { useNavigate } from 'react-router-dom';

export default function Logo({ size = 'md', className = '' }) {
  const navigate = useNavigate();
  const heights = { sm: 32, md: 40, lg: 56 };
  const h = heights[size] || heights.md;

  return (
    <img
      src="/logo.png"
      alt="ChapterWise"
      className={`site-logo ${className}`}
      style={{ height: h, width: 'auto', cursor: 'pointer', display: 'block' }}
      onClick={() => navigate('/')}
    />
  );
}
