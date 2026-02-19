import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AgentWorkspacePage } from "../pages/AgentWorkspacePage";
import { HomePage } from "../pages/HomePage";

export const AppRouter = () => (
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/agent" element={<AgentWorkspacePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </BrowserRouter>
);
