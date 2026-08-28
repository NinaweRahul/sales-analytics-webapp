export default function TopBar({ theme, toggleTheme, onLogoClick }) {
  return (
    <header className="topbar">
      <button type="button" className="topbar-brand" onClick={onLogoClick}>
        <span className="topbar-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 19V10M12 19V4M20 19V14" strokeLinecap="round" />
          </svg>
        </span>
        <span className="topbar-text">
          <span className="topbar-title">Sales Analytics</span>
          <span className="topbar-subtitle">Text-to-SQL · Powered by Gemini</span>
        </span>
      </button>

      <div className="topbar-right">
        <a
          href="https://ninawerahul.github.io"
          target="_blank"
          rel="noopener noreferrer"
          className="topbar-link"
        >
          Portfolio
        </a>
        <a
          href="https://github.com/NinaweRahul/sales-analytics-webapp"
          target="_blank"
          rel="noopener noreferrer"
          className="topbar-link"
        >
          GitHub
        </a>
        <button
          type="button"
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
      </div>
    </header>
  )
}
