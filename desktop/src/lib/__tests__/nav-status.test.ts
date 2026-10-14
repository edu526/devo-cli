import { describe, it, expect } from "vitest";
import { databasesAlertFor, profilesAlertFor } from "../nav-status";

describe("databasesAlertFor", () => {
  it("is quiet while every tunnel is fine", () => {
    expect(databasesAlertFor({ a: "connected", b: "stopped", c: "reconnecting" })).toBeNull();
  });

  it("points at failed tunnels first", () => {
    expect(databasesAlertFor({ a: "error", b: "expired_credentials" })).toEqual({
      level: "error",
      text: "1 tunnel failed",
    });
    expect(databasesAlertFor({ a: "error", b: "error" })?.text).toBe("2 tunnels failed");
  });

  it("then at tunnels waiting for a login", () => {
    expect(databasesAlertFor({ a: "expired_credentials", b: "connected" })).toEqual({
      level: "warning",
      text: "1 tunnel needs a login",
    });
    expect(databasesAlertFor({ a: "expired_credentials", b: "expired_credentials" })?.text).toBe(
      "2 tunnels need a login",
    );
  });
});

describe("profilesAlertFor", () => {
  it("points at SSO sessions that need a login", () => {
    expect(profilesAlertFor({})).toBeNull();
    expect(profilesAlertFor({ corp: ["a"] })).toEqual({ level: "warning", text: "AWS login required (1 session)" });
  });
});
