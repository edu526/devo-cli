import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import Switch from "../Switch.svelte";

describe("Switch", () => {
  let target: HTMLDivElement;
  let component: ReturnType<typeof mount> | undefined;

  beforeEach(() => {
    target = document.createElement("div");
    document.body.appendChild(target);
  });

  afterEach(() => {
    if (component) unmount(component);
    target.remove();
  });

  it("is a checkbox announced as a switch", () => {
    component = mount(Switch, { target, props: { checked: true, onchange: () => {} } });
    const input = target.querySelector("input")!;
    expect(input.type).toBe("checkbox");
    expect(input.getAttribute("role")).toBe("switch");
    expect(input.checked).toBe(true);
  });

  it("asks to change and keeps showing the saved value until the parent updates it", () => {
    const onchange = vi.fn();
    component = mount(Switch, { target, props: { checked: false, onchange } });
    const input = target.querySelector("input")!;

    input.click();
    flushSync();

    expect(onchange).toHaveBeenCalledOnce();
    // the save hasn't landed (or failed): still the saved value
    expect(input.checked).toBe(false);
  });
});
