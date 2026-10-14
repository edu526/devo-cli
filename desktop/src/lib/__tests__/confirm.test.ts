import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import { get } from "svelte/store";
import ConfirmDialog from "../ConfirmDialog.svelte";
import { answerConfirm, askConfirm, pendingConfirm } from "../confirm";

const question = { title: "Delete database?", message: '"db" is removed.', confirmLabel: "Delete", danger: true };

describe("askConfirm", () => {
  beforeEach(() => pendingConfirm.set(null));

  it("resolves with the answer and closes", async () => {
    const yes = askConfirm(question);
    answerConfirm(true);
    await expect(yes).resolves.toBe(true);
    expect(get(pendingConfirm)).toBeNull();

    const no = askConfirm(question);
    answerConfirm(false);
    await expect(no).resolves.toBe(false);
  });

  it("a new question cancels one still open", async () => {
    const first = askConfirm(question);
    const second = askConfirm({ ...question, title: "Other?" });

    await expect(first).resolves.toBe(false);
    expect(get(pendingConfirm)?.title).toBe("Other?");
    answerConfirm(true);
    await expect(second).resolves.toBe(true);
  });
});

describe("ConfirmDialog", () => {
  let target: HTMLDivElement;
  let component: ReturnType<typeof mount> | undefined;

  beforeEach(() => {
    pendingConfirm.set(null);
    target = document.createElement("div");
    document.body.appendChild(target);
    component = mount(ConfirmDialog, { target });
  });

  afterEach(() => {
    if (component) unmount(component);
    target.remove();
  });

  function ask() {
    const answer = askConfirm(question);
    flushSync();
    return answer;
  }

  it("shows nothing until asked, then the app's own dialog", () => {
    expect(target.querySelector("[role=alertdialog]")).toBeNull();

    void ask();

    expect(target.querySelector("h2")?.textContent).toBe("Delete database?");
    expect(target.textContent).toContain('"db" is removed.');
    expect(target.querySelector(".btn-danger")?.textContent?.trim()).toBe("Delete");
  });

  it("the action button confirms", async () => {
    const answer = ask();
    (target.querySelector(".btn-danger") as HTMLButtonElement).click();
    await expect(answer).resolves.toBe(true);
  });

  it("Cancel and Escape cancel", async () => {
    const byButton = ask();
    (target.querySelector(".btn-secondary") as HTMLButtonElement).click();
    await expect(byButton).resolves.toBe(false);

    const byEscape = ask();
    target
      .querySelector("[role=alertdialog]")!
      .dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await expect(byEscape).resolves.toBe(false);
  });
});
