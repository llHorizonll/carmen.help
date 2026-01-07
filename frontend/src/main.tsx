import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ChatProvider } from './context/ChatContext';
import ChatPage from './pages/ChatPage';
import StatsPage from './pages/StatsPage';
import ChromaAdminPage from './pages/ChromaAdminPage';
import CollectionManagerPage from './pages/CollectionManagerPage';
import '@chatui/core/dist/index.css';
import './styles/global.css';

// Suppress defaultProps warning from @chatui/core (third-party library issue)
const originalWarn = console.error;
console.error = (...args) => {
  if (args[0]?.includes?.('defaultProps')) return;
  originalWarn.apply(console, args);
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ChatProvider>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/admin/chroma" element={<ChromaAdminPage />} />
          <Route path="/admin/collections" element={<CollectionManagerPage />} />
        </Routes>
      </ChatProvider>
    </BrowserRouter>
  </React.StrictMode>
);
