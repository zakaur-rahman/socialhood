import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CropError, type Cropper } from "@/lib/publishing/crop";
import { assetInfo } from "@/test/composer-fixtures";

import { CropDialog } from "./CropDialog";

function renderCrop(cropper: Cropper, width = 3000, height = 1000) {
  const onCropped = vi.fn();
  const onOpenChange = vi.fn();
  render(
    <CropDialog
      open
      onOpenChange={onOpenChange}
      asset={assetInfo({ id: "wide", width, height })}
      label="Photo 3"
      source={{ file: null, url: "https://res.cloudinary.com/demo/wide.jpg", name: "wide.jpg" }}
      cropper={cropper}
      onCropped={onCropped}
    />,
  );
  return { onCropped, onOpenChange };
}

describe("CropDialog (TR-MED-02)", () => {
  it("starts on the nearest allowed shape and crops to it", async () => {
    const user = userEvent.setup();
    const file = new File(["c"], "wide-1x91x1.jpg", { type: "image/jpeg" });
    const cropper = vi.fn<Cropper>().mockResolvedValue(file);
    const { onCropped, onOpenChange } = renderCrop(cropper);
    expect(screen.getByRole("dialog", { name: "Crop Photo 3" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Landscape 1.91:1" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("crop-frame")).toHaveAttribute("data-rect", "545,0,1910,1000");
    await user.click(screen.getByRole("button", { name: "Crop and upload" }));
    expect(cropper).toHaveBeenCalledWith(
      { file: null, url: "https://res.cloudinary.com/demo/wide.jpg", name: "wide.jpg" },
      { x: 545, y: 0, width: 1910, height: 1000 },
      expect.objectContaining({ key: "1.91:1" }),
    );
    expect(onCropped).toHaveBeenCalledWith(file);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("says why when the image can't be cropped here", async () => {
    const user = userEvent.setup();
    const cropper = vi.fn<Cropper>().mockRejectedValue(new CropError("This image couldn't be opened for cropping."));
    const { onCropped } = renderCrop(cropper);
    await user.click(screen.getByRole("button", { name: "Crop and upload" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This image couldn't be opened for cropping.");
    expect(onCropped).not.toHaveBeenCalled();
  });

  it("moves the frame with the keyboard along the free side only", async () => {
    const user = userEvent.setup();
    renderCrop(vi.fn<Cropper>());
    const frame = screen.getByTestId("crop-frame");
    frame.focus();
    await user.keyboard("{ArrowRight}{ArrowDown}");
    const [x, y] = (frame.getAttribute("data-rect") ?? "").split(",").map(Number);
    expect(x).toBe(605);
    expect(y).toBe(0);
  });
});
