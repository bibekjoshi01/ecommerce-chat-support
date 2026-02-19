import { Link } from "react-router-dom";

export const AgentWorkspacePage = () => (
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

    <main className="agent-card">
      <h1>Agent Workspace Route Reserved</h1>
      <p>
        This route is wired for the next phase. Agent assignment, queue view, and
        real-time controls can be added here without changing customer routes.
      </p>
    </main>
  </div>
);
