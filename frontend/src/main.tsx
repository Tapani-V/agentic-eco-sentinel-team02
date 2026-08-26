import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';

// Styles
import './styles/tokens.css';
import './styles/base.css';
import './styles/components/header.css';
import './styles/components/kpi.css';
import './styles/components/tabs.css';
import './styles/components/cards.css';
import './styles/components/alerts.css';
import './styles/components/maintenance.css';
import './styles/components/states.css';
import './styles/components/responsive.css';
import './styles/components/charts.css';

// ---------------------------------------------------------------------------
// QueryClient with project defaults
// ---------------------------------------------------------------------------

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 10_000,
      gcTime: 15 * 60_000,
    },
  },
});

// ---------------------------------------------------------------------------
// RootErrorBoundary — catches unhandled render errors at the top level
// ---------------------------------------------------------------------------

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class RootErrorBoundary extends React.Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div role="alert" style={{ padding: '2rem', textAlign: 'center' }}>
          <h1>Something went wrong</h1>
          <p>{this.state.error?.message ?? 'An unexpected error occurred.'}</p>
          <button onClick={() => window.location.reload()}>Reload</button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// Mount
// ---------------------------------------------------------------------------

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <RootErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </RootErrorBoundary>
    </React.StrictMode>,
  );
}
