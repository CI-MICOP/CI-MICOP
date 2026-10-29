import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { Check, MapPin, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import Button from "../common/Button";
import Modal from "../common/Modal";

// OpenStreetMap - no API key, free for reasonable (non-bulk) use. See the
// usage policy: https://operations.osmfoundation.org/policies/tiles/ and
// https://operations.osmfoundation.org/policies/nominatim/. A production
// deployment with heavy traffic should run its own tile/geocoding
// service or a commercial provider instead of the public endpoints.
const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search";
const DEFAULT_CENTER = [20.5937, 78.9629]; // India, used only when no better center is known
const DEFAULT_ZOOM = 5;
const PIN_ZOOM = 16;

const pinIcon = L.divIcon({
  className: "",
  html:
    '<div style="width:28px;height:28px;transform:translate(-14px,-28px)">' +
    '<svg viewBox="0 0 24 24" fill="#dc2626" stroke="#7f1d1d" stroke-width="1"><path d="M12 2C7.58 2 4 5.58 4 10c0 5.25 6.4 11.44 7.1 12.1a1.3 1.3 0 0 0 1.8 0C13.6 21.44 20 15.25 20 10c0-4.42-3.58-8-8-8zm0 11a3 3 0 1 1 0-6 3 3 0 0 1 0 6z"/></svg>' +
    "</div>",
  iconSize: [28, 28],
  iconAnchor: [14, 28],
});

/**
 * An indoor-friendly fallback for recording evidence location: the
 * surveyor searches an address/place or clicks the map to drop a pin,
 * then explicitly confirms it. Never reports GPS accuracy for a
 * map-selected point and never claims the geocoder's address proves the
 * location - only that the surveyor picked that point.
 */
export default function LocationPicker({ initialLocation, onConfirm, onClose }) {
  const mapNodeRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const [picked, setPicked] = useState(
    initialLocation?.latitude != null ? { latitude: initialLocation.latitude, longitude: initialLocation.longitude } : null
  );
  const [addressLabel, setAddressLabel] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState({ status: "idle", results: [] });

  function placePin(latitude, longitude, pan = true) {
    setPicked({ latitude, longitude });
    const map = mapRef.current;
    if (!map) return;
    if (markerRef.current) {
      markerRef.current.setLatLng([latitude, longitude]);
    } else {
      markerRef.current = L.marker([latitude, longitude], { icon: pinIcon, draggable: true }).addTo(map);
      markerRef.current.on("dragend", () => {
        const { lat, lng } = markerRef.current.getLatLng();
        setPicked({ latitude: lat, longitude: lng });
      });
    }
    if (pan) map.setView([latitude, longitude], Math.max(map.getZoom(), PIN_ZOOM));
  }

  useEffect(() => {
    const center = picked ? [picked.latitude, picked.longitude] : DEFAULT_CENTER;
    const zoom = picked ? PIN_ZOOM : DEFAULT_ZOOM;
    const map = L.map(mapNodeRef.current, { center, zoom });
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map);
    mapRef.current = map;
    map.on("click", (event) => placePin(event.latlng.lat, event.latlng.lng));
    if (picked) placePin(picked.latitude, picked.longitude, false);
    // Leaflet sizes itself from the DOM at creation time; the modal's
    // layout settles a tick later, so re-measure once.
    const resize = () => map.invalidateSize();
    const timer = setTimeout(resize, 50);
    return () => {
      clearTimeout(timer);
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
    // Mounted once per picker instance - deliberately no deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runSearch(event) {
    event.preventDefault();
    const term = query.trim();
    if (!term) return;
    setSearch({ status: "loading", results: [] });
    try {
      const url = `${NOMINATIM_SEARCH_URL}?format=jsonv2&limit=5&q=${encodeURIComponent(term)}`;
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Search failed (${response.status})`);
      const results = await response.json();
      setSearch({ status: "done", results });
    } catch {
      // Address search is a convenience, not a requirement - manual
      // pin placement on the map still works when it is unavailable
      // (offline, blocked, or the public service is down).
      setSearch({ status: "error", results: [] });
    }
  }

  function chooseResult(result) {
    const latitude = Number(result.lat);
    const longitude = Number(result.lon);
    placePin(latitude, longitude);
    setAddressLabel(result.display_name ?? "");
    setSearch({ status: "idle", results: [] });
    setQuery(result.display_name ?? "");
  }

  function confirm() {
    if (!picked) return;
    onConfirm({ latitude: picked.latitude, longitude: picked.longitude, addressLabel: addressLabel.trim() || null });
  }

  return (
    <Modal isOpen onClose={onClose} title="Choose Location on Map" size="xl">
      <div className="space-y-3">
        <p className="text-xs text-muted">
          Search for an address or place, or click anywhere on the map to drop a pin. This location is recorded as{" "}
          <span className="font-medium text-ink">map-selected, not GPS-verified</span>.
        </p>

        <form onSubmit={runSearch} className="flex gap-2">
          <input
            className="input flex-1"
            placeholder="Search for an address or place"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search for an address or place"
          />
          <Button type="submit" variant="secondary" size="sm" isLoading={search.status === "loading"}>
            <Search className="h-4 w-4" aria-hidden="true" />
            Search
          </Button>
        </form>

        {search.status === "error" && (
          <p role="alert" className="text-xs text-amber-800">
            Address search is unavailable right now. You can still click the map to place a pin.
          </p>
        )}

        {search.results.length > 0 && (
          <ul className="max-h-36 overflow-y-auto rounded-card border border-border text-sm" aria-label="Search results">
            {search.results.map((result) => (
              <li key={result.place_id}>
                <button
                  type="button"
                  onClick={() => chooseResult(result)}
                  className="block w-full px-3 py-2 text-left hover:bg-surface"
                >
                  {result.display_name}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div ref={mapNodeRef} className="h-80 w-full overflow-hidden rounded-card border border-border" aria-label="Map" />

        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <p className="flex items-center gap-1.5 text-muted">
            <MapPin className="h-4 w-4 shrink-0" aria-hidden="true" />
            {picked
              ? `Selected: ${picked.latitude.toFixed(6)}, ${picked.longitude.toFixed(6)}`
              : "Click the map, or search above, to choose a location."}
          </p>
        </div>

        <div className="flex justify-end gap-3 border-t border-border pt-4">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={confirm} disabled={!picked}>
            <Check className="h-4 w-4" aria-hidden="true" />
            Confirm Location
          </Button>
        </div>
      </div>
    </Modal>
  );
}
