import { apiClient } from "./apiClient";

export async function getMyVehicles() {
  const response = await apiClient.get("/vehicles/me");
  return response.data;
}

export async function getVehicleById(vehicleId) {
  const response = await apiClient.get(`/vehicles/${vehicleId}`);
  return response.data;
}
