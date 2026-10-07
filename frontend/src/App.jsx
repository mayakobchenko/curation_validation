import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import NewValidation from './pages/NewValidation.jsx'
import ValidationForm from './pages/ValidationForm.jsx'
import TopBar from './components/TopBar.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <TopBar />
      <div className="page-shell">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewValidation />} />
          <Route path="/validations/:id" element={<ValidationForm />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
