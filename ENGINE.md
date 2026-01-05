# Technical Architecture & Engine

### 1. Frontend: ChatUI.io
- **Implementation:** React-based integration using `@chatui/core`.
- **UI Components:** Use `Card` components for rich responses (e.g., showing a "Feature Summary" card or "Step-by-step" card).
- **Theme:** Minimalist "Cloud Blue" to match Carmen Cloud branding.

### 2. LLM Gateway: Z.ai
- **Model:** `glm-4.7` (latest reasoning model).
- **Integration:** OpenAI-compatible SDK pointing to `https://api.z.ai/api/paas/v4/`.
- **Capabilities:** Utilizing "Thinking Mode" for complex multi-step help desk queries.

### 3. Knowledge Engine (RAG Pipeline)
- **Source:** Sync worker that pulls `.md` and `.mdx` files from `llHorizonll/docscarmencloud`.
- **Embedding:** Convert text to vectors using Z.ai embeddings (or HuggingFace `all-MiniLM-L6-v2`).
- **Vector DB:** Pinecone or ChromaDB to store the document embeddings.
- **Retrieval:** Semantic search based on user query intent.

### 4. Logic Flow
1. **User Input** → ChatUI.
2. **Query Analysis** → Z.ai identifies if it needs "Docs" or "General Chat".
3. **Retrieval** → Search Vector DB for Carmen Cloud documentation.
4. **Augmentation** → Prompt: `Based on these docs: {docs}, answer this user: {query}`.
5. **Output** → Streamed back to ChatUI.