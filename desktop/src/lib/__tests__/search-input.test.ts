import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, unmount } from "svelte";
import SearchInput from "../SearchInput.svelte";

describe("SearchInput", () => {
  let target: HTMLDivElement;
  let component: ReturnType<typeof mount> | undefined;

  beforeEach(() => {
    target = document.createElement("div");
    document.body.appendChild(target);
    vi.useFakeTimers();
  });

  afterEach(() => {
    if (component) unmount(component);
    target.remove();
    vi.useRealTimers();
  });

  it("renders an input with type=search", () => {
    component = mount(SearchInput, { target, props: { value: "" } });
    const input = target.querySelector("input");
    expect(input).not.toBeNull();
    expect(input?.type).toBe("search");
  });

  it("emits onchange after debounce delay", async () => {
    const onchange = vi.fn();
    component = mount(SearchInput, {
      target,
      props: { value: "", delay: 200, onchange },
    });
    const input = target.querySelector("input")!;
    input.value = "hello";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    // Not emitted yet
    expect(onchange).not.toHaveBeenCalled();
    // Fast-forward
    await vi.advanceTimersByTimeAsync(200);
    expect(onchange).toHaveBeenCalledWith("hello");
  });

  it("debounces repeated input into a single call", async () => {
    const onchange = vi.fn();
    component = mount(SearchInput, {
      target,
      props: { value: "", delay: 100, onchange },
    });
    const input = target.querySelector("input")!;
    input.value = "a";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await vi.advanceTimersByTimeAsync(50);
    input.value = "ab";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await vi.advanceTimersByTimeAsync(50);
    input.value = "abc";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await vi.advanceTimersByTimeAsync(100);
    expect(onchange).toHaveBeenCalledTimes(1);
    expect(onchange).toHaveBeenCalledWith("abc");
  });

  it("clear button resets the value and emits onchange('') immediately", async () => {
    const onchange = vi.fn();
    component = mount(SearchInput, {
      target,
      props: { value: "foo", onchange },
    });
    const clearBtn = target.querySelector<HTMLButtonElement>(".clear-btn")!;
    clearBtn.click();
    expect(onchange).toHaveBeenCalledWith("");
  });

  it("does not render clear button when value is empty", () => {
    component = mount(SearchInput, { target, props: { value: "" } });
    expect(target.querySelector(".clear-btn")).toBeNull();
  });

  it("renders clear button when value is non-empty", () => {
    component = mount(SearchInput, { target, props: { value: "x" } });
    expect(target.querySelector(".clear-btn")).not.toBeNull();
  });
});
