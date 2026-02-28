import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import App from './App'
import { AppLoader } from './components/common/AppLoader'
import './index.css'
import './styles/index.less'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 1,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AppLoader>
          <App />
        </AppLoader>
        <Toaster position="bottom-right" richColors />
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
