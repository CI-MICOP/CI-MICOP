import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LocationPicker from "../LocationPicker";

function jsonResponse(body, ok = true, status = 200) {
  return Promise.resolve({ ok, status, json: () => Promise.resolve(body) });
}

describe("LocationPicker", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("disables Confirm Location until a location is picked", async () => {
    render(<LocationPicker onConfirm={() => {}} onClose={() => {}} />);
    expect(await screen.findByRole("button", { name: /confirm location/i })).toBeDisabled();
  });

  it("starts with the location already picked when an initialLocation is given", async () => {
    render(
      <LocationPicker
        initialLocation={{ latitude: 13.08, longitude: 80.27 }}
        onConfirm={() => {}}
        onClose={() => {}}
      />
    );
    expect(await screen.findByText(/Selected: 13.080000, 80.270000/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirm location/i })).not.toBeDisabled();
  });

  it("searches for an address and picks the selected result", async () => {
    fetch.mockImplementationOnce(() =>
      jsonResponse([
        { place_id: 1, display_name: "Anna Salai, Chennai, Tamil Nadu", lat: "13.0612", lon: "80.2348" },
      ])
    );
    const onConfirm = vi.fn();
    render(<LocationPicker onConfirm={onConfirm} onClose={() => {}} />);

    fireEvent.change(screen.getByLabelText(/search for an address or place/i), { target: { value: "Anna Salai" } });
    fireEvent.click(screen.getByRole("button", { name: /^search$/i }));

    expect(await screen.findByText("Anna Salai, Chennai, Tamil Nadu")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Anna Salai, Chennai, Tamil Nadu"));

    expect(await screen.findByText(/Selected: 13.061200, 80.234800/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /confirm location/i }));
    expect(onConfirm).toHaveBeenCalledWith({
      latitude: 13.0612,
      longitude: 80.2348,
      addressLabel: "Anna Salai, Chennai, Tamil Nadu",
    });
  });

  it("still allows the map to be used when address search is unavailable", async () => {
    fetch.mockImplementationOnce(() => Promise.reject(new Error("network error")));
    render(<LocationPicker onConfirm={() => {}} onClose={() => {}} />);

    fireEvent.change(screen.getByLabelText(/search for an address or place/i), { target: { value: "somewhere" } });
    fireEvent.click(screen.getByRole("button", { name: /^search$/i }));

    expect(await screen.findByText(/address search is unavailable/i)).toBeInTheDocument();
    // The map itself (not search) is still present and the picker is usable.
    expect(screen.getByLabelText("Map")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirm location/i })).toBeDisabled();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const onClose = vi.fn();
    render(<LocationPicker onConfirm={() => {}} onClose={onClose} />);
    fireEvent.click(await screen.findByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("sends a null addressLabel when none was entered", async () => {
    const onConfirm = vi.fn();
    render(
      <LocationPicker
        initialLocation={{ latitude: 13.08, longitude: 80.27 }}
        onConfirm={onConfirm}
        onClose={() => {}}
      />
    );
    fireEvent.click(await screen.findByRole("button", { name: /confirm location/i }));
    expect(onConfirm).toHaveBeenCalledWith({ latitude: 13.08, longitude: 80.27, addressLabel: null });
  });
});
