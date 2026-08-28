import { useState, useEffect, useRef } from 'react'
import TopBar from './components/TopBar'
import Landing from './components/Landing'
import AskPanel from './components/AskPanel'
import ConversationTurn from './components/ConversationTurn'
import SchemaExplorer from './components/SchemaExplorer'
import { askQuestion } from './api'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function getInitialTheme() {
  const saved = localStorage.getItem('theme')
  if (saved) return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

let nextTurnId = 1

export default function App() {
  const [theme, setTheme] = useState(getInitialTheme)
  const [mode, setMode] = useState('landing')
  const [view, setView] = useState('ask')
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState([])
  const [serverStatus, setServerStatus] = useState('waking')
  const bottomRef = useRef(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((res) => setServerStatus(res.ok ? 'ready' : 'error'))
      .catch(() => setServerStatus('error'))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  function toggleTheme() {
    setTheme((t) => (t === 'light' ? 'dark' : 'light'))
  }

  function resetToLanding() {
    setMode('landing')
    setView('ask')
    setQuestion('')
    setHistory([])
  }

  async function handleAsk(q) {
    setMode('workspace')
    setView('ask')
    setQuestion('')

    const turnId = nextTurnId++
    setHistory((prev) => [...prev, { id: turnId, question: q, status: 'loading' }])

    try {
      const data = await askQuestion(q)
      setHistory((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, status: 'done', result: data } : t))
      )
    } catch (err) {
      setHistory((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, status: 'error', error: err.message } : t))
      )
    }
  }

  function handleExploreSchema() {
    setMode('workspace')
    setView('schema')
  }

  const isLoading = history.some((t) => t.status === 'loading')

  return (
    <div className="app-root">
      <TopBar theme={theme} toggleTheme={toggleTheme} onLogoClick={resetToLanding} />

      {mode === 'landing' && (
        <Landing
          question={question}
          setQuestion={setQuestion}
          onSubmit={handleAsk}
          loading={isLoading}
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
                loading={isLoading}
              />
            )}
          </div>

          <div className="workspace-main">
            {view === 'ask' && (
              <>
                {history.length === 0 && (
                  <div className="empty-state">Ask something to get started.</div>
                )}
                {history.map((turn) => (
                  <ConversationTurn key={turn.id} turn={turn} />
                ))}
                <div ref={bottomRef} />
              </>
            )}

            {view === 'schema' && (
              <>
                <p className="eyebrow">Star Schema · Olist E-Commerce</p>
                <h2 className="section-heading">Explore the database</h2>
                <SchemaExplorer />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}