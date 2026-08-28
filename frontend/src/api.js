const API_BASE = 'http://localhost:8000'

export async function askQuestion(question) {
  const response = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  const data = await response.json()

  if (!response.ok) {
    // FastAPI validation errors (422 from pydantic) return detail as an array;
    // our own HTTPException calls return detail as a string. Normalize both.
    const detail = Array.isArray(data.detail)
      ? data.detail.map((d) => d.msg).join(', ')
      : data.detail
    throw new Error(detail || `Request failed with status ${response.status}`)
  }

  return data
}
