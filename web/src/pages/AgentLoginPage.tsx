import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useLoginAgentMutation } from "../features/agent/api/agentApi";
import {
  loadStoredAgentSession,
  saveStoredAgentSession,
} from "../shared/lib/agentSession";
import "./AgentLoginPage.css";
import "./PageLayout.css";

const toErrorMessage = (error: unknown): string => {
  if (!error || typeof error !== "object") {
    return "Login failed. Please try again.";
  }
  if ("data" in error && typeof error.data === "object" && error.data !== null) {
    const payload = error.data as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  }
  if ("error" in error && typeof error.error === "string") {
    return error.error;
  }
  if ("message" in error && typeof error.message === "string") {
    return error.message;
  }
  return "Login failed. Please try again.";
};

export const AgentLoginPage = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [uiError, setUiError] = useState<string | null>(null);
  const [loginAgent, { isLoading }] = useLoginAgentMutation();

  useEffect(() => {
    const existing = loadStoredAgentSession();
    if (existing) {
      navigate("/agent", { replace: true });
    }
  }, [navigate]);

  const isSubmitDisabled = useMemo(
    () => isLoading || username.trim().length < 3 || password.length < 6,
    [isLoading, password.length, username],
  );

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setUiError(null);

    try {
      const response = await loginAgent({
        username: username.trim(),
        password,
      }).unwrap();
      saveStoredAgentSession({
        accessToken: response.access_token,
        expiresAt: response.expires_at,
        agentId: response.agent.id,
        displayName: response.agent.display_name,
        username: response.username,
      });
      navigate("/agent", { replace: true });
    } catch (error) {
      setUiError(toErrorMessage(error));
    }
  };

  return (
    <div className="agent-page">
      <header className="site-header">
        <Link className="brand" to="/">
          CommerceCare
        </Link>
        <nav className="top-nav">
          <Link className="top-nav-link" to="/">
            Customer Home
          </Link>
        </nav>
      </header>

      <main className="agent-login-shell">
        <section className="agent-login-card">
          <p className="agent-login-kicker">Agent Access</p>
          <h1>Sign in to agent workspace</h1>
          <p className="agent-login-subtitle">
            Use seeded credentials to enter the queue.
          </p>
          <p className="agent-login-helper">
            <code>admin</code> / <code>Admin@123</code>
          </p>

          <form className="agent-login-form" onSubmit={onSubmit}>
            <label className="agent-login-field">
              <span>Username</span>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                placeholder="admin"
                maxLength={80}
              />
            </label>

            <label className="agent-login-field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                placeholder="Enter password"
                maxLength={128}
              />
            </label>

            {uiError && <div className="agent-login-error">{uiError}</div>}

            <button className="agent-login-submit" type="submit" disabled={isSubmitDisabled}>
              {isLoading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
};
