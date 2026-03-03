export default function LoadingOverlay({ message = 'Please wait...' }) {
  return (
    <div className="loading-overlay">
      <div className="loading-box">
        <div className="spinner" />
        <p className="loading-message">{message}</p>
      </div>
    </div>
  );
}
