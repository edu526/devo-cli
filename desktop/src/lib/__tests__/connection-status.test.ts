import { describe, it, expect } from "vitest";
import { explainError, stateLabel } from "../connection-status";

describe("stateLabel", () => {
  it("names every state the tunnels report", () => {
    expect(stateLabel("expired_credentials")).toBe("Login needed");
    expect(stateLabel("error")).toBe("Failed");
    expect(stateLabel("connected")).toBe("Connected");
    expect(stateLabel("reconnecting")).toBe("Reconnecting");
  });

  it("never shows a raw identifier for an unknown state", () => {
    expect(stateLabel("half_open")).toBe("half open");
  });
});

describe("explainError", () => {
  it("has nothing to explain without an error", () => {
    expect(explainError(null)).toBeNull();
    expect(explainError("   ")).toBeNull();
  });

  it("explains known AWS errors and keeps the original as detail", () => {
    const raw =
      "An error occurred (TargetNotConnected) when calling the StartSession operation: i-0abc123 is not connected.";
    expect(explainError(raw)).toEqual({
      summary: "The bastion isn't reachable through SSM: it may be stopped, or its SSM agent is offline.",
      detail: raw,
    });
  });

  it("names the missing profile", () => {
    expect(explainError("The config profile (orders-db) could not be found")?.summary).toBe(
      'The AWS profile "orders-db" isn\'t in your AWS config.',
    );
  });

  it("explains the tunnel loop's own messages, with no detail that repeats them", () => {
    expect(explainError("Failed to connect after 5 attempts. Aborting.")).toEqual({
      summary: "Couldn't connect after 5 tries.",
      detail: null,
    });
    expect(explainError("Session ended")).toEqual({ summary: "The SSM session ended.", detail: null });
  });

  it("tells a missing plugin from one that stopped", () => {
    expect(
      explainError(
        "SessionManagerPlugin is not found. Please refer to SessionManager Documentation here: https://docs.aws.amazon.com",
      )?.summary,
    ).toBe("The AWS Session Manager plugin isn't installed.");

    const stopped =
      "aws: [ERROR]: Command '['session-manager-plugin', 'AWS_SSM_START_SESSION_RESPONSE', 'us-east-1', 'StartSession', " +
      "'epicride-db-prod', '{\"Target\": \"i-02875c39a3a3b1921\"}', 'https://ssm.us-east-1.amazonaws.com']' " +
      "returned non-zero exit status 15.";
    expect(explainError(stopped)).toEqual({
      summary: "The SSM session closed (the Session Manager plugin stopped with code 15).",
      detail: stopped,
    });
  });

  it("explains a local port taken by another program", () => {
    expect(explainError("[WinError 10048] Only one usage of each socket address is normally permitted")?.summary).toBe(
      "Its local port is already used by another program.",
    );
  });

  it("drops the AWS CLI boilerplate from an unknown AWS error", () => {
    const raw = "An error occurred (ThrottlingException) when calling the StartSession operation: Rate exceeded";
    expect(explainError(raw)).toEqual({ summary: "Rate exceeded", detail: raw });
  });

  it("shows an unknown message as it is, without a duplicate detail", () => {
    expect(explainError("Something odd happened")).toEqual({ summary: "Something odd happened", detail: null });
  });
});
