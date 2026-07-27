import { Link } from "react-router-dom";

import { Button } from "../components/ui/Button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--page-bg)] px-4 text-center">
      <div>
        <div className="brand-gradient-text text-7xl font-extrabold">404</div>
        <h1 className="mt-4 text-2xl font-bold text-[var(--text-primary)]">Page not found</h1>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">The requested EyeAI workspace does not exist.</p>
        <Link to="/">
          <Button className="mt-6">Return to dashboard</Button>
        </Link>
      </div>
    </div>
  );
}
