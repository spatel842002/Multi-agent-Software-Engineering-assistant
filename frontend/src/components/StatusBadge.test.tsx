import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders the status text with underscores replaced by spaces", () => {
    render(<StatusBadge status="pending_approval" />);
    expect(screen.getByText("pending approval")).toBeInTheDocument();
  });

  it("falls back to a neutral style for an unknown status", () => {
    render(<StatusBadge status="something_unexpected" />);
    expect(screen.getByText("something unexpected")).toBeInTheDocument();
  });
});
