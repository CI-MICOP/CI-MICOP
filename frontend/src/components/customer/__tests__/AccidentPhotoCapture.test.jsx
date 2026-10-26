import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AccidentPhotoCapture from "../AccidentPhotoCapture";
import { MAX_ACCIDENT_PHOTOS } from "../documentCategories";
import { installCamera, removeCamera } from "./cameraMock";

let camera;

afterEach(() => {
  camera?.restore();
  camera = null;
});

function Harness({ initial = [], onChange = () => {} }) {
  const [photos, setPhotos] = useState(initial);
  return (
    <AccidentPhotoCapture
      photos={photos}
      onChange={(next) => {
        setPhotos(next);
        onChange(next);
      }}
    />
  );
}

function photo(name) {
  return new File(["\xff\xd8\xff"], name, { type: "image/jpeg" });
}

async function openCameraAndTakePhoto() {
  fireEvent.click(screen.getByRole("button", { name: /open camera/i }));
  const take = await screen.findByRole("button", { name: /^take photo$/i });
  await waitFor(() => expect(take).toBeEnabled());
  fireEvent.click(take);
}

describe("AccidentPhotoCapture", () => {
  it("has no file input, so existing images cannot be chosen", () => {
    camera = installCamera();
    const { container } = render(<Harness />);
    expect(container.querySelector('input[type="file"]')).toBeNull();
  });

  it("takes a JPEG photo from the rear camera and adds it to the list", async () => {
    camera = installCamera();
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await openCameraAndTakePhoto();

    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const [photos] = onChange.mock.calls.at(-1);
    expect(photos).toHaveLength(1);
    expect(photos[0].type).toBe("image/jpeg");
    expect(camera.getUserMedia).toHaveBeenCalledWith({ video: { facingMode: { ideal: "environment" } }, audio: false });
    expect(screen.getByText(`1 of ${MAX_ACCIDENT_PHOTOS} photos taken`)).toBeInTheDocument();
  });

  it("retakes and removes a captured photo", async () => {
    camera = installCamera();
    const onChange = vi.fn();
    render(<Harness initial={[photo("first.jpg"), photo("second.jpg")]} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Retake photo 1" }));
    const replace = await screen.findByRole("button", { name: "Take replacement for photo 1" });
    await waitFor(() => expect(replace).toBeEnabled());
    fireEvent.click(replace);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    let [photos] = onChange.mock.calls.at(-1);
    expect(photos).toHaveLength(2);
    expect(photos[0].name).toMatch(/^accident-photo-/);
    expect(photos[1].name).toBe("second.jpg");

    fireEvent.click(screen.getByRole("button", { name: "Remove photo 2" }));
    [photos] = onChange.mock.calls.at(-1);
    expect(photos.map((p) => p.name)).toEqual([expect.stringMatching(/^accident-photo-/)]);
  });

  it("explains a denied camera permission and offers no upload instead", async () => {
    camera = installCamera({ error: Object.assign(new Error("denied"), { name: "NotAllowedError" }) });
    const { container } = render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: /open camera/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/camera access was blocked/i);
    expect(container.querySelector('input[type="file"]')).toBeNull();
  });

  it("explains a missing camera", async () => {
    camera = installCamera({ error: Object.assign(new Error("none"), { name: "NotFoundError" }) });
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: /open camera/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/no camera was found/i);
  });

  it("explains a camera that is in use elsewhere", async () => {
    camera = installCamera({ error: Object.assign(new Error("busy"), { name: "NotReadableError" }) });
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: /open camera/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/being used by another app/i);
  });

  it("explains an unsupported browser", () => {
    camera = removeCamera();
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: /open camera/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/can't open the camera here/i);
  });

  it("reports a failed capture without adding a photo", async () => {
    camera = installCamera();
    const restoreBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = (callback) => callback(null);
    try {
      const onChange = vi.fn();
      render(<Harness onChange={onChange} />);
      await openCameraAndTakePhoto();
      expect(await screen.findByRole("alert")).toHaveTextContent(/could not be captured/i);
      expect(onChange).not.toHaveBeenCalled();
      await waitFor(() => expect(screen.getByRole("button", { name: /^take photo$/i })).toBeEnabled());
    } finally {
      HTMLCanvasElement.prototype.toBlob = restoreBlob;
    }
  });

  it("stops the camera when closed", async () => {
    camera = installCamera();
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: /open camera/i }));
    fireEvent.click(await screen.findByRole("button", { name: /close camera/i }));
    expect(camera.track.stop).toHaveBeenCalled();
  });

  it("does not open the camera once the photo limit is reached", () => {
    camera = installCamera();
    const full = Array.from({ length: MAX_ACCIDENT_PHOTOS }, (_, i) => photo(`p${i}.jpg`));
    render(<Harness initial={full} />);
    expect(screen.getByRole("button", { name: /open camera/i })).toBeDisabled();
  });
});
