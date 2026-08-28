import { useEffect, useState, useMemo } from 'react'
import ReactFlow, { Background, Controls, MarkerType } from 'reactflow'
import 'reactflow/dist/style.css'
import TableNode from './TableNode'

const API_BASE = 'http://localhost:8000'

const nodeTypes = { tableNode: TableNode }

// Manual layout -- dimensions on top, fact_order_items centered below
// (it's the table with FK edges to all four dimensions), payments/reviews
// below that (connected to fact_order_items only by shared order_id,
// not an enforced FK -- see the dashed edge styling for those).
const POSITIONS = {
  'analytics.dim_customers': { x: 0, y: 0 },
  'analytics.dim_products': { x: 280, y: 0 },
  'analytics.dim_sellers': { x: 560, y: 0 },
  'analytics.dim_date': { x: 840, y: 0 },
  'analytics.fact_order_items': { x: 420, y: 420 },
  'analytics.fact_payments': { x: 140, y: 760 },
  'analytics.fact_reviews': { x: 700, y: 760 },
}

export default function SchemaExplorer() {
  const [schema, setSchema] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/schema`)
      .then((res) => {
        if (!res.ok) throw new Error(`Schema request failed: ${res.status}`)
        return res.json()
      })
      .then(setSchema)
      .catch((err) => setError(err.message))
  }, [])

  const { nodes, edges } = useMemo(() => {
    if (!schema) return { nodes: [], edges: [] }

    const nodes = schema.tables.map((table) => ({
      id: table.name,
      type: 'tableNode',
      position: POSITIONS[table.name] || { x: 0, y: 0 },
      data: table,
    }))

    const edges = schema.relationships.map((rel, i) => ({
      id: `edge-${i}`,
      source: rel.from_table,
      target: rel.to_table,
      label: `${rel.from_column} → ${rel.to_column}`,
      labelStyle: { fontSize: 10, fontFamily: 'var(--font-mono)' },
      style: {
        stroke: rel.kind === 'foreign_key' ? 'var(--color-accent)' : 'var(--color-ink-muted)',
        strokeDasharray: rel.kind === 'logical' ? '4 4' : undefined,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--color-ink-muted)' },
    }))

    return { nodes, edges }
  }, [schema])

  if (error) {
    return <div className="status-message error">Couldn't load schema: {error}</div>
  }

  if (!schema) {
    return <div className="empty-state">Loading schema…</div>
  }

  return (
    <div className="schema-explorer">
      <p className="schema-explorer-note">
        Solid lines are enforced foreign keys. Dashed lines are tables that share a
        column value (<code className="mono">order_id</code>) without a database
        constraint — hover a table to see why.
      </p>
      <div className="schema-flow-wrap">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--color-border)" gap={20} />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  )
}