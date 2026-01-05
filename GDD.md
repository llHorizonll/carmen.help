# General Design Document (GDD)

## Vision
A seamless, "human-like" help desk assistant embedded in the Carmen Cloud webapp that reduces support tickets by providing instant, accurate manual lookups.

## Visual Design
- **Chat Launcher:** A floating action button (FAB) at the bottom right.
- **Chat Window:**
    - Header: "Carmen AI Assistant" with a "Green/Online" status.
    - Message Bubble: White for Assistant, Carmen-Blue for User.
- **Rich Elements:** - Use `chatui.io/card` to display "Quick Links" to documentation chapters.
    - Use code blocks with "Copy" buttons for technical instructions.

## Key Interaction Features
- **Auto-Suggest:** Provides 3 common questions (e.g., "How do I set up billing?", "What is the site policy?") upon opening.
- **Source Citations:** Every answer must include a link back to the specific page on `docscarmencloud.vercel.app`.