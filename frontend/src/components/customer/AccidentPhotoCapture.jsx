import { Camera, CameraOff, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import Button from "../common/Button";
import { MAX_ACCIDENT_PHOTOS, MAX_UPLOAD_BYTES } from "./documentCategories";

// Longest side of a captured photo. Keeps a phone-camera frame well under
// the upload size limit without losing the detail a reviewer needs.
const MAX_DIMENSION = 1920;
const JPEG_QUALITY = 0.85;

function cameraErrorMessage(error) {
  switch (error?.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Camera access was blocked. Allow camera access for this site in your browser settings, then try again.";
    case "NotFoundError":
    case "OverconstrainedError":
    case "DevicesNotFoundError":
      return "No camera was found on this device. Accident photos need a device with a camera.";
    case "NotReadableError":
    case "TrackStartError":
      return "The camera is being used by another app or could not be started. Close other apps using it and try again.";
    default:
      return "The camera could not be opened. Please try again.";
  }
}

function PhotoPreview({ file, label }) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    let cancelled = false;
    const reader = new FileReader();
    reader.onload = () => {
      if (!cancelled) setSrc(String(reader.result));
    };
    reader.readAsDataURL(file);
    return () => {
      cancelled = true;
    };
  }, [file]);

  return src ? (
    <img src={src} alt={label} className="aspect-video w-full rounded-card border border-border object-cover" />
  ) : (
    <div className="flex aspect-video items-center justify-center rounded-card border border-border text-xs text-muted">
      {label}
    </div>
  );
}

function cameraSupported() {
  return typeof navigator !== "undefined" && typeof navigator.mediaDevices?.getUserMedia === "function";
}

function captureFrame(video) {
  return new Promise((resolve, reject) => {
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) {
      reject(new Error("The camera isn't ready yet - wait a moment and try again."));
      return;
    }
    const scale = Math.min(1, MAX_DIMENSION / Math.max(width, height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const context = canvas.getContext("2d");
    if (!context) {
      reject(new Error("The photo could not be captured. Please try again."));
      return;
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("The photo could not be captured. Please try again."))),
      "image/jpeg",
      JPEG_QUALITY
    );
  });
}

/**
 * Takes accident photos with the device camera (getUserMedia). There is
 * deliberately no file input and no fallback to one: if the camera can't be
 * used, the customer is told why and no photo can be added. Captured photos
 * are JPEG files handed to `onChange`; nothing is uploaded here.
 *
 * Capturing through the camera does not prove when or where a photo was
 * taken, or that it is genuine - it only stops existing images being chosen
 * from a gallery in this form.
 */
export default function AccidentPhotoCapture({ photos, onChange, disabled = false }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [cameraState, setCameraState] = useState("idle"); // idle | starting | live
  const [error, setError] = useState("");
  const [retakeIndex, setRetakeIndex] = useState(null);
  const [isCapturing, setIsCapturing] = useState(false);

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraState("idle");
    setRetakeIndex(null);
  }

  useEffect(() => () => streamRef.current?.getTracks().forEach((track) => track.stop()), []);

  async function startCamera(nextRetakeIndex = null) {
    setError("");
    setRetakeIndex(nextRetakeIndex);
    if (streamRef.current) {
      setCameraState("live");
      return;
    }
    if (!cameraSupported()) {
      setError(
        "This browser can't open the camera here. Use an up-to-date browser on a device with a camera, on a secure (https) connection. Accident photos can only be taken with the camera."
      );
      return;
    }
    setCameraState("starting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      streamRef.current = stream;
      setCameraState("live");
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play?.();
      }
    } catch (err) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setCameraState("idle");
      setRetakeIndex(null);
      setError(cameraErrorMessage(err));
    }
  }

  // Attach the stream once the <video> element is rendered.
  useEffect(() => {
    if (cameraState === "live" && videoRef.current && streamRef.current && !videoRef.current.srcObject) {
      videoRef.current.srcObject = streamRef.current;
      Promise.resolve(videoRef.current.play?.()).catch(() => {});
    }
  }, [cameraState]);

  async function takePhoto() {
    if (isCapturing || !videoRef.current) return;
    setIsCapturing(true);
    setError("");
    try {
      const blob = await captureFrame(videoRef.current);
      if (blob.size > MAX_UPLOAD_BYTES) {
        throw new Error("The photo is larger than the 10 MB upload limit. Please try again.");
      }
      const file = new File([blob], `accident-photo-${Date.now()}.jpg`, { type: "image/jpeg" });
      if (retakeIndex !== null) {
        onChange(photos.map((photo, index) => (index === retakeIndex ? file : photo)));
        stopCamera();
      } else {
        onChange([...photos, file]);
        if (photos.length + 1 >= MAX_ACCIDENT_PHOTOS) stopCamera();
      }
    } catch (err) {
      setError(err.message || "The photo could not be captured. Please try again.");
    } finally {
      setIsCapturing(false);
    }
  }

  function removePhoto(index) {
    onChange(photos.filter((_, i) => i !== index));
    if (retakeIndex === index) setRetakeIndex(null);
  }

  const atLimit = photos.length >= MAX_ACCIDENT_PHOTOS;
  const cameraOpen = cameraState === "live" || cameraState === "starting";

  return (
    <div className="space-y-3 rounded-card border border-border bg-surface p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-muted" aria-live="polite">
          {photos.length} of {MAX_ACCIDENT_PHOTOS} photos taken
        </p>
        {!cameraOpen ? (
          <Button size="sm" onClick={() => startCamera()} disabled={disabled || atLimit}>
            <Camera className="h-4 w-4" aria-hidden="true" />
            Open camera
          </Button>
        ) : (
          <Button size="sm" variant="secondary" onClick={stopCamera} disabled={disabled}>
            <CameraOff className="h-4 w-4" aria-hidden="true" />
            Close camera
          </Button>
        )}
      </div>

      {error && (
        <p role="alert" className="rounded-card border border-red-200 bg-red-50 p-3 text-red-900">
          {error}
        </p>
      )}

      {cameraOpen && (
        <div className="space-y-2">
          {cameraState === "starting" && <p className="text-muted">Starting the camera...</p>}
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            aria-label="Camera preview"
            className="aspect-video w-full rounded-card bg-black object-contain"
          />
          <Button onClick={takePhoto} disabled={disabled || cameraState !== "live" || isCapturing} isLoading={isCapturing}>
            <Camera className="h-4 w-4" aria-hidden="true" />
            {retakeIndex !== null ? `Take replacement for photo ${retakeIndex + 1}` : "Take photo"}
          </Button>
        </div>
      )}

      {photos.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {photos.map((photo, index) => (
            <li key={`${photo.name}-${index}`} className="space-y-1.5">
              <PhotoPreview file={photo} label={`Accident photo ${index + 1}`} />
              <div className="flex gap-1.5">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={disabled}
                  onClick={() => startCamera(index)}
                  aria-label={`Retake photo ${index + 1}`}
                >
                  <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                  Retake
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={disabled}
                  onClick={() => removePhoto(index)}
                  aria-label={`Remove photo ${index + 1}`}
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Remove
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
