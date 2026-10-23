import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EMPTY_FORM } from "./label";
import { OperatorForm } from "./OperatorForm";

describe("OperatorForm", () => {
  it("blocks Continue without a consent reference, then submits the label", () => {
    const onSubmit = vi.fn();
    render(<OperatorForm initial={{ ...EMPTY_FORM, person: "P01", device: "D01" }} busy={false} error={null} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("The consent reference is required.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Consent reference"), { target: { value: "CF-9" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onSubmit).toHaveBeenCalledWith(
      { person: "P01", device: "D01", light: "normal", kind: "genuine", tool: null, set: "A", consent_ref: "CF-9" },
      expect.objectContaining({ consent_ref: "CF-9" }),
    );
  });

  it("never asks for a name", () => {
    render(<OperatorForm initial={EMPTY_FORM} busy={false} error={null} onSubmit={() => undefined} />);
    for (const el of screen.getAllByRole("textbox")) {
      const name = el.getAttribute("id") ?? "";
      expect(name.toLowerCase()).not.toContain("name");
    }
    expect(screen.queryByLabelText(/name/i)).toBeNull();
  });
});
