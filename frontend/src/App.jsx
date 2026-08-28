import { useState, useEffect } from 'react'
import TopBar from './components/TopBar'
import Landing from './components/Landing'
import AskPanel from './components/AskPanel'
import ResultsTabs from './components/ResultsTabs'
import SchemaExplorer from './components/SchemaExplorer'
import { askQuestion } from './api'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function getInitialTheme() {
  const saved = localStorage.getItem('theme')
  if (saved) return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export default function App() {
  const [theme, setTheme] = useState(getInitialTheme)
  const [mode, setMode] = useState('landing') // 'landing' | 'workspace'
  const [view, setView] = useState('ask') // 'ask' | 'schema' (only relevant in workspace)
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  // 'waking' | 'ready' | 'error' -- Render's free tier spins down when idle,
  // so the first request after a while can take 30-60s. Pinging /health on
  // mount wakes it up in the background before the user asks anything, and
  // the landing page's status pill reflects this so the wait isn't silent.
  const [serverStatus, setServerStatus] = useState('waking')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((res) => setServerStatus(res.ok ? 'ready' : 'error'))
      .catch(() => setServerStatus('error'))
  }, [])

  function toggleTheme() {
    setTheme((t) => (t === 'light' ? 'dark' : 'light'))
  }

  function resetToLanding() {
    setMode('landing')
    setView('ask')
    setQuestion('')
    setResult(null)
    setError(null)
  }

  async function handleAsk(q) {
    setMode('workspace')
    setView('ask')
    setQuestion(q)
    setLoading(true)
    setError(null)
    try {
      const data = await askQuestion(q)
      setResult(data)
    } catch (err) {
      setError(err.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  function handleExploreSchema() {
    setMode('workspace')
    setView('schema')
  }

  return (
    <div className="app-root">
      <TopBar theme={theme} toggleTheme={toggleTheme} onLogoClick={resetToLanding} />

      {mode === 'landing' && (
        <Landing
          question={question}
          setQuestion={setQuestion}
          onSubmit={handleAsk}
          loading={loading}
          onExploreSchema={handleExploreSchema}
          serverStatus={serverStatus}
        />
      )}

      {mode === 'workspace' && (
        <div className="workspace-shell">
          <div className="workspace-sidebar">
            <div className="view-switch">
              <button
                className={`view-switch-btn ${view === 'ask' ? 'active' : ''}`}
                onClick={() => setView('ask')}
              >
                Ask
              </button>
              <button
                className={`view-switch-btn ${view === 'schema' ? 'active' : ''}`}
                onClick={() => setView('schema')}
              >
                Explore Schema
              </button>
            </div>

            {view === 'ask' && (
              <AskPanel
                question={question}
                setQuestion={setQuestion}
                onSubmit={handleAsk}
                loading={loading}
              />
            )}
          </div>

          <div className="workspace-main">
            {view === 'ask' && (
              <>
                <h1 style={{ marginBottom: 20 }}>{result ? result.question : question}</h1>

                {loading && (
                  <div className="status-message loading">
                    Generating SQL and running the analysis — this can take a few seconds…
                  </div>
                )}

                {error && <div className="status-message error">{error}</div>}

                {result && !loading && <ResultsTabs result={result} />}
              </>
            )}

            {view === 'schema' && (
              <>
                <p className="eyebrow">Star Schema · Olist E-Commerce</p>
                <h1 style={{ marginBottom: 20 }}>Explore the database</h1>
                <SchemaExplorer />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}