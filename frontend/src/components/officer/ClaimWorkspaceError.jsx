import ErrorState from "../common/ErrorState";
import { getApiErrorMessage } from "../../utils/errors";

export default function ClaimWorkspaceError({ title = "Unable to load this claim", error, onRetry }) {
  return (
    <ErrorState
      title={error?.response?.status === 403 ? "Access denied" : error?.response?.status === 404 ? "Claim not found" : title}
      message={getApiErrorMessage(error)}
      onRetry={onRetry}
    />
  );
}
