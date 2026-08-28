const STEPS = [
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
    title: 'Ask',
    desc: 'Type a question in plain English about the order data — no SQL knowledge needed.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M16 18l6-6-6-6M8 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    title: 'Generate SQL',
    desc: 'Gemini writes and validates a query against the real schema — no write access, ever.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    title: 'Verify',
    desc: 'Every answer shows its exact SQL and the raw data — nothing is hidden.',
  },
]

export default function Landing({ question, setQuestion, onSubmit, loading, onExploreSchema }) {
  function handleSubmit(e) {
    e.preventDefault()
    if (question.trim() && !loading) onSubmit(question.trim())
  }

  return (
    <div className="landing-container">
      <p className="eyebrow landing-eyebrow">Text-to-SQL · Powered by Gemini</p>
      <h1 className="landing-headline">
        Ask anything about <em>real order data</em>
      </h1>
      <p className="landing-subtext">
        Ask a question in plain English and get a verified SQL answer.
        <br />
        No dashboards to build, no queries to write — just ask.
      </p>

      <div className="status-pill">
        <span className="status-dot" />
        113,000 real orders, ready to query
      </div>

      <form className="landing-ask-card" onSubmit={handleSubmit}>
        <textarea
          className="landing-textarea"
          placeholder="e.g. What are the top 10 products by revenue?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          autoFocus
        />
        <button className="ask-button" type="submit" disabled={loading || !question.trim()}>
          {loading ? 'Thinking…' : 'Ask'}
        </button>
      </form>

      <button type="button" className="landing-schema-link" onClick={onExploreSchema}>
        or explore the database schema →
      </button>

      <div className="steps-grid">
        {STEPS.map((step, i) => (
          <div className="step-card" key={step.title}>
            <div className="step-num">{String(i + 1).padStart(2, '0')}</div>
            <div className="step-icon-box">{step.icon}</div>
            <div className="step-title">{step.title}</div>
            <div className="step-desc">{step.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
