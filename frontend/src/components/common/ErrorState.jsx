import { AlertTriangle } from "lucide-react";

import Button from "./Button";

export default function ErrorState({
  title = "Something went wrong",
  message = "Please try again in a moment.",
  onRetry,
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center" role="alert">
      <AlertTriangle className="h-6 w-6 text-danger" aria-hidden="true" />
      <div>
        <p className="font-medium text-ink">{title}</p>
        <p className="text-sm text-muted">{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
