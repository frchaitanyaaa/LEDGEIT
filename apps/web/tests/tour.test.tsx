import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useTour } from "../src/lib/tour";

beforeEach(() => localStorage.clear());
afterEach(cleanup);

describe("useTour", () => {
  it("opens by itself on the first visit, and not again once finished", () => {
    const first = renderHook(() => useTour());
    expect(first.result.current.running).toBe(true);
    act(() => first.result.current.finish());
    expect(first.result.current.running).toBe(false);
    const second = renderHook(() => useTour());
    expect(second.result.current.running).toBe(false);
    expect(second.result.current.enabled).toBe(true);
  });

  it("can be switched off, and back on to replay", () => {
    const { result } = renderHook(() => useTour());
    act(() => result.current.setEnabled(false));
    expect(result.current.running).toBe(false);
    expect(result.current.enabled).toBe(false);
    expect(renderHook(() => useTour()).result.current.running).toBe(false);
    act(() => result.current.setEnabled(true));
    expect(result.current.running).toBe(true);
  });
});
