import { Camera, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import Button from "../common/Button";
import { CAMERA_CONSTRAINTS, CAMERA_UNSUPPORTED_MESSAGE, cameraErrorMessage, cameraSupported } from "./cameraSupport";

/**
 * A live device-camera preview with a Capture button. It opens the camera
 * when it mounts and releases it (stops every track) when it unmounts or is
 * closed. The camera stays open between captures, so several photos can be
 * taken in a row.
 *
 * onCapture(blob, capturedAt) receives each photo; onClose() closes it.
 */
export default function CameraView({ onCapture, onClose }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [state, setState] = useState(() => (cameraSupported() ? { status: "starting" } : { status: "error", message: CAMERA_UNSUPPORTED_MESSAGE }));

  useEffect(() => {
    if (!cameraSupported()) return undefined;
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia(CAMERA_CONSTRAINTS)
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        setState({ status: "live" });
      })
      .catch((error) => {
        if (!cancelled) setState({ status: "error", message: cameraErrorMessage(error) });
      });
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };
  }, []);

  // Attach the stream once the <video> element is on screen.
  useEffect(() => {
    if (state.status === "live" && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
      // play() returns a promise in current browsers but not everywhere.
      const playing = videoRef.current.play?.();
      playing?.catch?.(() => {});
    }
  }, [state.status]);

  function capture() {
    const video = videoRef.current;
    const width = video?.videoWidth;
    const height = video?.videoHeight;
    if (!width || !height) {
      setState({ status: "live", notice: "The camera is not ready yet. Wait a moment and capture again." });
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      setState({ status: "live", notice: "This browser could not capture a photo from the camera." });
      return;
    }
    context.drawImage(video, 0, 0, width, height);
    const capturedAt = new Date().toISOString();
    canvas.toBlob(
      (blob) => {
        if (blob) onCapture(blob, capturedAt);
        else setState({ status: "live", notice: "The photo could not be captured. Please try again." });
      },
      "image/jpeg",
      0.9
    );
  }

  if (state.status === "error") {
    return (
      <div className="space-y-3">
        <p role="alert" className="rounded-card border border-red-200 bg-red-50 p-3 text-sm text-danger">
          {state.message}
        </p>
        <Button variant="secondary" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {state.status === "starting" && <p className="text-sm text-muted">Starting camera...</p>}
      {state.status === "live" && (
        <video
          ref={videoRef}
          data-testid="camera-preview"
          autoPlay
          playsInline
          muted
          className="aspect-video w-full max-w-xl rounded-card bg-black object-cover"
        />
      )}
      {state.notice && (
        <p role="alert" className="text-sm text-amber-800">
          {state.notice}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <Button onClick={capture} disabled={state.status !== "live"}>
          <Camera className="h-4 w-4" aria-hidden="true" />
          Capture
        </Button>
        <Button variant="secondary" onClick={onClose}>
          <X className="h-4 w-4" aria-hidden="true" />
          Close camera
        </Button>
      </div>
    </div>
  );
}
