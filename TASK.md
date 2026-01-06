# Project Implementation Tasks

## Phase 1: Knowledge Base Prep
- [x] Create a Python script to clone `llHorizonll/docscarmencloud`.
- [x] Parse Markdown files into chunks (split by headers).
- [x] Generate embeddings and upload to Vector DB.

## Phase 2: Backend Development
- [x] Setup Express.js or FastAPI server.
- [x] Integrate Z.ai API using the `OpenAI` client wrapper.
- [x] Implement the RAG retrieval logic (Search DB -> Context -> LLM).

## Phase 3: Frontend Integration
- [x] Install `@chatui/core` in the webapp project.
- [x] Create the `ChatContainer` and `Message` components.
- [ ] Implement `Card` rendering for documentation snippets.

## Phase 4: Multi-Agent Logic
- [ ] Define System Prompts for Librarian, Expert, and Executor agents.
- [ ] Implement "Verification" step to check LLM output against source docs.

## Phase 5: Deployment
- [ ] Deploy backend to Vercel/Render.
- [ ] Add the Chat Widget to the main Carmen Cloud production site.

## Phase 6: Analytics & Observability
- [x] Implement chat session logging (SQLite storage).
- [x] Add message history with sources tracking.
- [x] Create chat statistics endpoint (`/api/chat/stats`).
- [x] Track token usage (prompt, completion, total tokens).
- [x] Track LLM response time.
- [x] Display usage stats on frontend (tokens + response time).
- [x] Create separate Chat page (`/`) with bubble-style usage stats.
- [x] Create Statistics page (`/stats`) for viewing chat logs and analytics.
- [x] Add navigation between pages with react-router-dom.

## Phase 7: Admin Tools
- [x] Create ChromaDB Admin API endpoints (`/api/admin/chroma/*`).
- [x] Implement collection listing and stats.
- [x] Add document browsing with pagination.
- [x] Add semantic search functionality for documents.
- [x] Add document deletion capability.
- [x] Create ChromaDB Admin UI page (`/admin/chroma`).
- [x] Add collections sidebar with document counts.
- [x] Add documents table with metadata display.
- [x] Add document detail modal view.
- [x] Add navigation links between all pages.