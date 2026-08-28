const SUGGESTED_QUESTIONS = [
  'What are the top 10 products by revenue?',
  'How many customers have placed more than one order?',
  'What is the average review score by product category?',
  'Which states generate the most revenue?',
  'What percentage of orders were delivered late?',
]

export default function AskPanel({ question, setQuestion, onSubmit, loading }) {
  function handleSubmit(e) {
    e.preventDefault()
    if (question.trim() && !loading) onSubmit(question.trim())
  }

  return (
    <>
      <form className="ask-form" onSubmit={handleSubmit}>
        <textarea
          className="ask-textarea"
          placeholder="Ask a question about the sales data..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="ask-button" type="submit" disabled={loading || !question.trim()}>
          {loading ? 'Thinking…' : 'Ask'}
        </button>
      </form>

      <div className="suggested-questions">
        <div className="suggested-label">Try asking</div>
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            className="suggested-chip"
            onClick={() => onSubmit(q)}
            disabled={loading}
          >
            {q}
          </button>
        ))}
      </div>
    </>
  )
}
