import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FileUpload from "./FileUpload";

describe("FileUpload", () => {
  it("renders dropzone with instructions", () => {
    render(<FileUpload onSubmit={vi.fn()} />);

    expect(screen.getByText(/Drag & drop video or images here/)).toBeInTheDocument();
    expect(screen.getByText(/MP4, MOV, AVI/)).toBeInTheDocument();
  });

  it("renders method selector with default splatfacto", () => {
    render(<FileUpload onSubmit={vi.fn()} />);

    const select = screen.getByRole("combobox");
    expect(select).toHaveValue("splatfacto");
  });

  it("has both Gaussian Splatting and NeRF options", () => {
    render(<FileUpload onSubmit={vi.fn()} />);

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent("Gaussian Splatting");
    expect(options[1]).toHaveTextContent("NeRF");
  });

  it("submit button is disabled when no files are selected", () => {
    render(<FileUpload onSubmit={vi.fn()} />);

    expect(screen.getByText("Start Reconstruction")).toBeDisabled();
  });

  it("shows 'Uploading...' when disabled", () => {
    render(<FileUpload onSubmit={vi.fn()} disabled />);

    expect(screen.getByText("Uploading...")).toBeInTheDocument();
    expect(screen.getByText("Uploading...")).toBeDisabled();
  });

  it("allows method selection change", async () => {
    const user = userEvent.setup();
    render(<FileUpload onSubmit={vi.fn()} />);

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "nerfacto");
    expect(select).toHaveValue("nerfacto");
  });
});
