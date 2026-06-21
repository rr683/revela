import { BrowserRouter, Routes, Route } from "react-router-dom";
import { JobsProvider } from "./context/JobsContext";
import Dashboard from "./pages/Dashboard";
import JobDetail from "./pages/JobDetail";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <JobsProvider>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/jobs/:jobId" element={<JobDetail />} />
        </Routes>
      </JobsProvider>
    </BrowserRouter>
  );
}
