import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { loadStoredAgentSession } from "../../../shared/lib/agentSession";

interface RequireAgentAuthProps {
  children: ReactNode;
}

export const RequireAgentAuth = ({ children }: RequireAgentAuthProps) => {
  const session = loadStoredAgentSession();
  if (!session) {
    return <Navigate to="/agent/login" replace />;
  }
  return children;
};
