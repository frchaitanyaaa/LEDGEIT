import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { InspectionLink } from "../src/components/InspectionLink";
import { Sheet } from "../src/components/Sheet";
import { useWorkspace } from "../src/lib/workspace";

afterEach(cleanup);

function Probe() {
  const w = useWorkspace();
  const loc = useLocation();
  return (
    <div>
      <span data-testid="url">{loc.search}</span>
      <button onClick={() => w.openPanel("risk")}>panel</button>
      <button onClick={() => w.openInspection("abc")}>inspection</button>
      <button onClick={w.closeTop}>close</button>
      <InspectionLink id="xyz">link</InspectionLink>
    </div>
  );
}

describe("useWorkspace", () => {
  it("closes the inspection first, then the panel underneath", () => {
    render(<MemoryRouter><Probe /></MemoryRouter>);
    fireEvent.click(screen.getByText("panel"));
    fireEvent.click(screen.getByText("inspection"));
    expect(screen.getByTestId("url").textContent).toBe("?panel=risk&inspection=abc");
    fireEvent.click(screen.getByText("close"));
    expect(screen.getByTestId("url").textContent).toBe("?panel=risk");
    fireEvent.click(screen.getByText("close"));
    expect(screen.getByTestId("url").textContent).toBe("");
  });

  it("InspectionLink keeps the open panel", () => {
    render(<MemoryRouter initialEntries={["/?panel=overrides"]}><Probe /></MemoryRouter>);
    expect(screen.getByText("link").getAttribute("href")).toBe("/?panel=overrides&inspection=xyz");
  });
});

describe("Sheet", () => {
  it("only the top-most sheet closes on Escape", () => {
    const calls: string[] = [];
    render(
      <>
        <Sheet title="Panel" onClose={() => calls.push("panel")}>a</Sheet>
        <Sheet title="Inspection" level={2} onClose={() => calls.push("inspection")}>b</Sheet>
      </>,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(calls).toEqual(["inspection"]);
  });

  it("closes from the close button and the backdrop", () => {
    let n = 0;
    const { container } = render(<Sheet title="T" onClose={() => n++}>x</Sheet>);
    fireEvent.click(screen.getByLabelText("Close"));
    fireEvent.click(container.querySelector(".sheet-backdrop")!);
    expect(n).toBe(2);
  });
});
