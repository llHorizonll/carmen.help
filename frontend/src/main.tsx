import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import '@chatui/core/dist/index.css';

// Suppress defaultProps warning from @chatui/core (third-party library issue)
const originalWarn = console.error;
console.error = (...args) => {
  if (args[0]?.includes?.('defaultProps')) return;
  originalWarn.apply(console, args);
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
