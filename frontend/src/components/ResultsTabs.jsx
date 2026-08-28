import { useState } from 'react'
import SimpleBarChart from './SimpleBarChart'

const TABS = ['Explanation', 'SQL', 'Data', 'Chart']

export default function ResultsTabs({ result }) {
  const [activeTab, setActiveTab] = useState('Explanation')

  return (
    <div className="results-card">
      <div className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab}
            className={`tab-button ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="tab-panel">
        {activeTab === 'Explanation' && (
          <p className="explanation-text">{result.explanation}</p>
        )}

        {activeTab === 'SQL' && (
          <pre className="sql-panel">{result.sql}</pre>
        )}

        {activeTab === 'Data' && (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  {result.columns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j}>{cell === null ? '—' : String(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'Chart' && (
          <SimpleBarChart columns={result.columns} rows={result.rows} />
        )}
      </div>

      <div className="row-count-note">
        {result.row_count} row{result.row_count !== 1 ? 's' : ''} returned
        {result.generation_attempts > 1 && ` · took ${result.generation_attempts} attempts to generate valid SQL`}
      </div>
    </div>
  )
}
