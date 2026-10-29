import { ImageOff } from "lucide-react";
import { useEffect, useState } from "react";

import { getClaimEvidenceImage } from "../../services/officerService";

/**
 * Thumbnail of one evidence photo on a claim the officer is authorized to
 * view. Fetched through the API (an <img> cannot send the bearer token),
 * re-authorized against this exact claim on every request - mirrors
 * components/surveyor/EvidenceThumbnail.jsx for the officer's own,
 * claim-scoped endpoint.
 */
export default function EvidenceThumbnail({ claimId, evidenceId, alt }) {
  const [state, setState] = useState({ status: "loading", url: null });

  useEffect(() => {
    let url = null;
    let cancelled = false;
    getClaimEvidenceImage(claimId, evidenceId)
      .then((blob) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setState({ status: "ready", url });
      })
      .catch(() => !cancelled && setState({ status: "error", url: null }));
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [claimId, evidenceId]);

  if (state.status === "ready") return <img src={state.url} alt={alt} className="aspect-[4/3] w-full object-cover" />;
  return (
    <div className="flex aspect-[4/3] w-full items-center justify-center bg-surface text-muted" aria-label={alt}>
      {state.status === "error" ? <ImageOff className="h-5 w-5" aria-hidden="true" /> : <span className="text-xs">Loading...</span>}
    </div>
  );
}
