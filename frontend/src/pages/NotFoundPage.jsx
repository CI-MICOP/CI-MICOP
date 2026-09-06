import { Link } from "react-router-dom";

import Button from "../components/common/Button";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-surface px-4 text-center">
      <p className="text-3xl font-semibold text-ink">404</p>
      <p className="text-sm text-muted">The page you're looking for doesn't exist.</p>
      <Link to="/">
        <Button variant="secondary">Go home</Button>
      </Link>
    </div>
  );
}
