import { vi } from "vitest";

// jsdom has no camera, no video frames and no canvas drawing. These stand-ins
// let a test drive AccidentPhotoCapture: a fake stream, a fixed video frame
// size, and a canvas that "encodes" a small JPEG blob.
export function installCamera({ error = null } = {}) {
  const track = { stop: vi.fn() };
  const stream = { getTracks: () => [track] };
  const getUserMedia = error ? vi.fn().mockRejectedValue(error) : vi.fn().mockResolvedValue(stream);
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });

  const restores = [
    stub(HTMLMediaElement.prototype, "play", { value: vi.fn().mockResolvedValue(undefined) }),
    stub(HTMLVideoElement.prototype, "videoWidth", { get: () => 1280 }),
    stub(HTMLVideoElement.prototype, "videoHeight", { get: () => 720 }),
    stub(HTMLCanvasElement.prototype, "getContext", { value: () => ({ drawImage: vi.fn() }) }),
    stub(HTMLCanvasElement.prototype, "toBlob", {
      value(callback, type) {
        callback(new Blob(["\xff\xd8\xff jpeg"], { type }));
      },
    }),
  ];
  return {
    getUserMedia,
    track,
    restore() {
      restores.forEach((undo) => undo());
      delete navigator.mediaDevices;
    },
  };
}

export function removeCamera() {
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
  return { restore: () => delete navigator.mediaDevices };
}

function stub(target, key, descriptor) {
  const original = Object.getOwnPropertyDescriptor(target, key);
  Object.defineProperty(target, key, { configurable: true, ...descriptor });
  return () => {
    if (original) Object.defineProperty(target, key, original);
    else delete target[key];
  };
}
