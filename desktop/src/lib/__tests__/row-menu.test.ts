import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import RowMenu from "../RowMenu.svelte";

describe("RowMenu", () => {
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

  function open() {
    flushSync(); // let the mount's effects run (bindings)
    target.querySelector<HTMLButtonElement>(".row-menu-btn")!.click();
    flushSync();
  }

  const items = (onEdit = vi.fn(), onDelete = vi.fn()) => [
    { label: "Edit", onselect: onEdit },
    { label: "Delete", onselect: onDelete, danger: true },
  ];

  it("shows its actions only once opened", () => {
    component = mount(RowMenu, { target, props: { items: items() } });
    expect(document.querySelector('[role="menu"]')).toBeNull();

    open();

    const labels = [...document.querySelectorAll('[role="menuitem"]')].map((b) => b.textContent?.trim());
    expect(labels).toEqual(["Edit", "Delete"]);
    expect(target.querySelector(".row-menu-btn")!.getAttribute("aria-expanded")).toBe("true");
  });

  it("runs the chosen action and closes", () => {
    const onDelete = vi.fn();
    component = mount(RowMenu, { target, props: { items: items(vi.fn(), onDelete) } });
    open();

    document.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')[1]!.click();
    flushSync();

    expect(onDelete).toHaveBeenCalledOnce();
    expect(document.querySelector('[role="menu"]')).toBeNull();
  });

  it("closes on Escape without running anything", () => {
    const onEdit = vi.fn();
    component = mount(RowMenu, { target, props: { items: items(onEdit) } });
    open();

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    flushSync();

    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("closes on a click elsewhere", () => {
    component = mount(RowMenu, { target, props: { items: items() } });
    open();

    document.body.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    flushSync();

    expect(document.querySelector('[role="menu"]')).toBeNull();
  });
});
