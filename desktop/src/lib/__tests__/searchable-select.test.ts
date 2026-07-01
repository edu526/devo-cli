import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, unmount } from "svelte";
import SearchableSelect from "../SearchableSelect.svelte";

const sampleOptions = [
  { value: "111", label: "Project Alpha | Tooling (111111111111)" },
  { value: "222", label: "Shared Service | Dev (222222222222)" },
  { value: "333", label: "Project Beta (333333333333)" },
  { value: "444", label: "Customer Portal | Prod (444444444444)" },
  { value: "555", label: "Project Alpha | Dev (555555555555)" },
  { value: "666", label: "Machine Learning – Dev (666666666666)" },
];

function makeInputEvent(input: HTMLInputElement, value: string) {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("SearchableSelect", () => {
  let target: HTMLDivElement;
  let component: ReturnType<typeof mount> | undefined;

  beforeEach(() => {
    target = document.createElement("div");
    document.body.appendChild(target);
  });

  afterEach(() => {
    if (component) unmount(component);
    target.remove();
    vi.restoreAllMocks();
  });

  it("renders the input with the selected option's label when closed", () => {
    component = mount(SearchableSelect, {
      target,
      props: { options: sampleOptions, value: "333" },
    });
    const input = target.querySelector("input")!;
    expect(input.value).toBe("Project Beta (333333333333)");
  });

  it("renders the placeholder when no option is selected", () => {
    component = mount(SearchableSelect, {
      target,
      props: { options: sampleOptions, value: "", placeholder: "Search accounts…" },
    });
    const input = target.querySelector("input")!;
    expect(input.value).toBe("");
    expect(input.placeholder).toBe("Search accounts…");
  });

  it("opens the dropdown on focus and shows all options", async () => {
    component = mount(SearchableSelect, {
      target,
      props: { options: sampleOptions, value: "" },
    });
    const input = target.querySelector("input")!;
    input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
    await Promise.resolve();
    const options = target.querySelectorAll('[role="option"]');
    expect(options).toHaveLength(6);
  });

  it("filters options by case-insensitive substring on the label", async () => {
    component = mount(SearchableSelect, {
      target,
      props: { options: sampleOptions, value: "" },
    });
    const input = target.querySelector("input")!;
    input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
    await Promise.resolve();
    makeInputEvent(input, "alpha");
    await Promise.resolve();
    const options = Array.from(
      target.querySelectorAll('[role="option"]'),
    ) as HTMLElement[];
    expect(options).toHaveLength(2);
    const labels = options.map((o) => o.textContent);
    expect(labels.every((l) => l && l.toLowerCase().includes("alpha"))).toBe(true);
  });

  it("matches by account ID inside the label", async () => {
    component = mount(SearchableSelect, {
      target,
      props: { options: sampleOptions, value: "" },
    });
    const input = target.querySelector("input")!;
    input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
    await Promise.resolve();
    makeInputEvent(input, "111111111111");
    await Promise.resolve();
    const options = target.querySelectorAll('[role="option"]');
    expect(options).toHaveLength(1);
  });

  it("shows an empty state when nothing matches", async () => {
    component = mount(SearchableSelect, {
      target,
      props: { options: sampleOptions, value: "" },
    });
    const input = target.querySelector("input")!;
    input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
    await Promise.resolve();
    makeInputEvent(input, "zzz");
    await Promise.resolve();
    expect(target.querySelectorAll('[role="option"]')).toHaveLength(0);
    expect(target.querySelector(".empty")?.textContent).toBe("No matches");
  });

  it("emits onchange with the selected value on click", async () => {
    const onchange = vi.fn();
    component = mount(SearchableSelect, {
      target,
      props: { options: sampleOptions, value: "", onchange },
    });
    const input = target.querySelector("input")!;
    input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
    await Promise.resolve();
    const options = Array.from(
      target.querySelectorAll('[role="option"]'),
    ) as HTMLElement[];
    const targetOpt = options.find((o) =>
      o.textContent?.includes("Project Beta"),
    )!;
    targetOpt.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    expect(onchange).toHaveBeenCalledWith("333");
  });

  it("navigates with ArrowDown/ArrowUp and selects with Enter", async () => {
    const onchange = vi.fn();
    component = mount(SearchableSelect, {
      target,
      props: { options: sampleOptions, value: "", onchange },
    });
    const input = target.querySelector("input")!;
    input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
    await Promise.resolve();
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(onchange).toHaveBeenCalledWith("222");
  });

  it("closes the dropdown on Escape without changing the value", async () => {
    const onchange = vi.fn();
    component = mount(SearchableSelect, {
      target,
      props: { options: sampleOptions, value: "333", onchange },
    });
    const input = target.querySelector("input")!;
    input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
    await Promise.resolve();
    expect(target.querySelectorAll('[role="option"]').length).toBeGreaterThan(0);
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await Promise.resolve();
    expect(target.querySelectorAll('[role="option"]')).toHaveLength(0);
    expect(onchange).not.toHaveBeenCalled();
  });

  it("does not open when disabled", async () => {
    component = mount(SearchableSelect, {
      target,
      props: { options: sampleOptions, value: "", disabled: true },
    });
    const input = target.querySelector("input")!;
    input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
    await Promise.resolve();
    expect(target.querySelectorAll('[role="option"]')).toHaveLength(0);
  });
});
