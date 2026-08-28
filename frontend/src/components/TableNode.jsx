import { Handle, Position } from 'reactflow'

// Custom node: renders one database table as a card with its column list.
// Styled with the same CSS variables as the rest of the app (portfolio
// tokens), so it doesn't look like a bolted-on third-party widget.
export default function TableNode({ data }) {
  const shortName = data.name.replace('analytics.', '')
  const isFact = shortName.startsWith('fact_')

  return (
    <div className={`schema-node ${isFact ? 'schema-node-fact' : 'schema-node-dim'}`}>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />

      <div className="schema-node-header">
        <span className="schema-node-badge">{isFact ? 'FACT' : 'DIM'}</span>
        {shortName}
      </div>
      <div className="schema-node-grain">{data.grain}</div>
      <div className="schema-node-columns">
        {data.columns.map((col) => (
          <div className="schema-node-column" key={col.name} title={col.description}>
            <span className="col-name">{col.name}</span>
            <span className="col-type mono">{col.dtype}</span>
          </div>
        ))}
      </div>
    </div>
  )
}