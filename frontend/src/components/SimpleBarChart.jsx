// Deliberately no charting library -- for a single-series "top N" bar
// chart, a handful of divs is simpler and lighter than pulling in a
// dependency. If the app grows more chart types later, revisit this.
export default function SimpleBarChart({ columns, rows }) {
  // Find the first numeric column to chart against the first column as label.
  const numericColIndex = columns.findIndex((_, i) =>
    rows.every((row) => typeof row[i] === 'number' || !isNaN(parseFloat(row[i])))
  )

  if (numericColIndex === -1 || rows.length === 0) {
    return <div className="empty-state">This result isn't chart-friendly — check the Data tab instead.</div>
  }

  const labelColIndex = numericColIndex === 0 && columns.length > 1 ? 1 : 0
  const values = rows.map((row) => parseFloat(row[numericColIndex]))
  const maxValue = Math.max(...values)

  return (
    <div className="bar-chart">
      {rows.slice(0, 15).map((row, i) => {
        const value = values[i]
        const pct = maxValue > 0 ? (value / maxValue) * 100 : 0
        return (
          <div className="bar-row" key={i}>
            <div className="bar-label" title={String(row[labelColIndex])}>
              {String(row[labelColIndex])}
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <div className="bar-value numeric">{value.toLocaleString()}</div>
          </div>
        )
      })}
    </div>
  )
}
