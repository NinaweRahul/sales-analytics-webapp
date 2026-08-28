import ResultsTabs from './ResultsTabs'

// One self-contained block per question asked, stacked in order (oldest to
// newest) -- same idea as a chat thread, but each "message" is a full
// results panel rather than a text bubble.
export default function ConversationTurn({ turn }) {
  return (
    <div className="turn-block">
      <div className="turn-question">{turn.question}</div>

      {turn.status === 'loading' && (
        <div className="status-message loading">
          Generating SQL and running the analysis — this can take a few seconds…
        </div>
      )}

      {turn.status === 'error' && (
        <div className="status-message error">{turn.error}</div>
      )}

      {turn.status === 'done' && <ResultsTabs result={turn.result} />}
    </div>
  )
}