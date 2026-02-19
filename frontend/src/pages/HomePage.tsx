import { Link } from "react-router-dom";

import { CustomerChatWidget } from "../features/chat/ui/CustomerChatWidget";

export const HomePage = () => (
  <div className="home-page">
    <header className="site-header">
      <Link className="brand" to="/">
        CommerceCare
      </Link>
      <nav className="top-nav">
        <Link className="top-nav-link" to="/agent">
          Agent Workspace
        </Link>
      </nav>
    </header>

    <main className="hero-shell">
      <section className="hero-card">
        <p className="hero-kicker">Customer support experience</p>
        <h1>Fast answers without leaving checkout flow</h1>
        <p>
          This customer surface uses a floating support widget pattern. It stays
          lightweight on the page and opens into a focused live-support flow
          when customers need help.
        </p>
      </section>
    </main>

    <CustomerChatWidget />
  </div>
);
