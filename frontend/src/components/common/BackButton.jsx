import { ArrowLeft } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import Button from "./Button";

/**
 * Returns to the previous in-app page when one exists in this tab's
 * history, otherwise falls back to a safe, in-app destination instead of
 * leaving the application. React Router gives every history entry a
 * random `key`, except the one the browser loaded directly into (a fresh
 * visit, a refresh of that same entry, or an external link) - that entry
 * alone keeps the literal key "default", which is how this tells "came
 * from elsewhere in the app" apart from "landed here directly."
 */
export default function BackButton({ fallback, className = "" }) {
  const navigate = useNavigate();
  const location = useLocation();

  function handleClick() {
    if (location.key !== "default") {
      navigate(-1);
    } else {
      navigate(fallback);
    }
  }

  return (
    <Button variant="ghost" size="sm" onClick={handleClick} className={`mb-4 ${className}`}>
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Back
    </Button>
  );
}
