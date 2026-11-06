import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import './styles/theme.css'
import { App } from './app/App'
import { AuthProvider } from './lib/auth'
import { queryClient } from './lib/query'
import { StepUpProvider } from './app/StepUp'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <StepUpProvider>
            <App />
          </StepUpProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
