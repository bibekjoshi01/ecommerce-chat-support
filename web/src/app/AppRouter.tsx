import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { RequireAgentAuth } from "../features/agent/ui/RequireAgentAuth";
import { AgentLoginPage } from "../pages/AgentLoginPage";
import { AgentWorkspacePage } from "../pages/AgentWorkspacePage";
import { HomePage } from "../pages/HomePage";

export const AppRouter = () => (
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/agent/login" element={<AgentLoginPage />} />
      <Route
        path="/agent"
        element={
          <RequireAgentAuth>
            <AgentWorkspacePage />
          </RequireAgentAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </BrowserRouter>
);
