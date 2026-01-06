# Testing Guide

Manual testing procedures for Carmen.help features.

---

## Backend API Testing

### Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy", "service": "Carmen.help API", "version": "0.1.0"}
```

### Chat Endpoint

```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I set up billing?", "stream": false}'
```

Expected: Response with `answer`, `sources`, `session_id`, and `usage` fields.

### Chat Statistics

```bash
curl http://localhost:8000/api/chat/stats
```

Expected: Response with `total_sessions`, `total_messages`, `sessions_today`.

---

## ChromaDB Admin API Testing

### Get ChromaDB Stats

```bash
curl http://localhost:8000/api/admin/chroma/stats
```

Expected response:
```json
{
  "persist_directory": "./data/chroma",
  "total_collections": 1,
  "total_documents": 245,
  "collections": [{"name": "carmen_docs", "count": 245, "metadata": {}}]
}
```

### List Collections

```bash
curl http://localhost:8000/api/admin/chroma/collections
```

Expected: Array of collection objects with `name`, `count`, `metadata`.

### Get Collection Info

```bash
curl http://localhost:8000/api/admin/chroma/collections/carmen_docs
```

Expected: Single collection object with `name`, `count`, `metadata`.

### List Documents (Paginated)

```bash
# First page
curl "http://localhost:8000/api/admin/chroma/collections/carmen_docs/documents?offset=0&limit=10"

# Second page
curl "http://localhost:8000/api/admin/chroma/collections/carmen_docs/documents?offset=10&limit=10"
```

Expected response:
```json
{
  "total": 245,
  "offset": 0,
  "limit": 10,
  "documents": [
    {"id": "doc-1", "document": "...", "metadata": {...}},
    ...
  ]
}
```

### Semantic Search

```bash
curl "http://localhost:8000/api/admin/chroma/collections/carmen_docs/search?q=billing&top_k=5"
```

Expected: Array of search results with `id`, `document`, `metadata`, `distance`, `similarity`.

### Get Single Document

```bash
curl http://localhost:8000/api/admin/chroma/collections/carmen_docs/documents/{document_id}
```

Expected: Single document object with `id`, `document`, `metadata`.

### Delete Document

```bash
curl -X DELETE http://localhost:8000/api/admin/chroma/collections/carmen_docs/documents/{document_id}
```

Expected: `{"message": "Document '{document_id}' deleted successfully"}`

---

## Frontend Testing

### Pages

| Route | Test |
|-------|------|
| `/` | Chat page loads, suggestions display, messages send/receive |
| `/stats` | Stats load, sessions list, click to view messages |
| `/admin/chroma` | Collections load, documents display, search works |

### Chat Page (`/`)

1. Page loads with header "Carmen AI Assistant"
2. Quick reply suggestions appear
3. Click suggestion sends message
4. Type message and press Enter
5. Response appears with sources
6. Usage stats show (tokens, response time)

### Statistics Page (`/stats`)

1. Stats cards display totals
2. Sessions list loads
3. Click session to view messages
4. Delete session removes from list
5. Back to Chat link works

### ChromaDB Admin Page (`/admin/chroma`)

1. Stats cards show collections/documents count
2. Collections sidebar displays all collections
3. Click collection to browse documents
4. Pagination works (Previous/Next)
5. Search returns relevant documents with similarity scores
6. Click document row opens detail modal
7. Delete document removes from list
8. Navigation links to Stats and Chat work

---

## Integration Testing

### Full Chat Flow

1. Start backend: `cd backend && uvicorn main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:5173
4. Send a message about Carmen Cloud
5. Verify response includes sources
6. Check usage stats appear
7. Go to /stats and verify session logged
8. Go to /admin/chroma and search for terms from your message

### Vector Store Verification

```bash
cd backend

# Check stats
python -m knowledge_base.vector_store --action stats

# Test search
python -m knowledge_base.vector_store --action search --query "billing setup"
```

---

## Error Scenarios

### Backend Not Running

- Frontend should show error message on chat send
- Admin page should display error banner

### Empty Collection

- Admin page should show "No documents" state
- Pagination should be hidden

### Invalid Search Query

- Empty search should be prevented (disabled button)
- Search with no results should show empty table

### 404 Errors

- Non-existent collection: 404 with message
- Non-existent document: 404 with message

---

## Performance Checks

| Metric | Target |
|--------|--------|
| Chat response time | < 5 seconds |
| Admin page load | < 2 seconds |
| Document list (20 items) | < 500ms |
| Semantic search | < 1 second |
