import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ErrorBox, Table, errorMessage } from "../src/components/ui";
import { ApiError } from "../src/lib/api";

afterEach(cleanup);

describe("Table", () => {
  it("shows a spinner while loading instead of the empty text", () => {
    render(<Table head={["A"]} loading empty emptyText="No rows">{null}</Table>);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(screen.queryByText("No rows")).not.toBeInTheDocument();
  });

  it("shows page-specific empty text, falling back to the default", () => {
    const { rerender } = render(<Table head={["A"]} empty emptyText="No open alerts.">{null}</Table>);
    expect(screen.getByText("No open alerts.")).toBeInTheDocument();
    rerender(<Table head={["A"]} empty>{null}</Table>);
    expect(screen.getByText("Nothing here yet.")).toBeInTheDocument();
  });
});

describe("ErrorBox", () => {
  it("renders nothing without an error", () => {
    const { container } = render(<ErrorBox error={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a readable message and calls onRetry", () => {
    const retry = vi.fn();
    render(<ErrorBox error={new ApiError(503, "HTTP_ERROR", "Service Unavailable")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("The server ran into a problem (503)");
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("has no retry button when onRetry is not given", () => {
    render(<ErrorBox error={new Error("boom")} />);
    expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
  });
});

describe("errorMessage", () => {
  it("maps API and network failures to plain sentences", () => {
    expect(errorMessage(new ApiError(403, "FORBIDDEN", "forbidden"))).toBe("Your role does not have access to this.");
    expect(errorMessage(new ApiError(401, "UNAUTHORIZED", "x"))).toMatch(/sign in again/);
    expect(errorMessage(new ApiError(409, "CONFLICT", "Override already decided"))).toBe("Override already decided");
    expect(errorMessage(new TypeError("Failed to fetch"))).toMatch(/Cannot reach the LEDGEIT API/);
    expect(errorMessage("plain")).toBe("plain");
  });
});
