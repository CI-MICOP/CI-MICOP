import { apiClient } from "./apiClient";
import { getCustomerById } from "./customerService";
import { getPolicyById } from "./policyService";
import { getVehicleById } from "./vehicleService";

export async function listClaimsForProcessing(params = {}) {
  const response = await apiClient.get("/officer/claims", { params });
  return response.data;
}

export async function getClaimProcessingDetail(claimId) {
  const response = await apiClient.get(`/officer/claims/${claimId}`);
  return response.data;
}

// Claims Officer/Admin are authorized to read full customer, vehicle, and
// policy records (unlike Surveyor, who is explicitly blocked) - this
// composes the claim-processing aggregate with those three lookups for
// the Claim Details workspace and its tabs.
export async function getClaimWorkspaceData(claimId) {
  const detail = await getClaimProcessingDetail(claimId);
  const { claim } = detail;
  const [customer, vehicle, policy] = await Promise.all([
    getCustomerById(claim.Customer_ID).catch(() => null),
    getVehicleById(claim.Vehicle_ID).catch(() => null),
    getPolicyById(claim.Policy_ID).catch(() => null),
  ]);
  return { ...detail, customer, vehicle, policy };
}
