/**
 * What a tunnel's state and error mean, in words a user can act on. The raw
 * error (usually the AWS CLI's first stderr line) stays available as detail.
 */

const STATE_LABELS: Record<string, string> = {
  connected: "Connected",
  starting: "Starting",
  connecting: "Connecting",
  reconnecting: "Reconnecting",
  expired_credentials: "Login needed",
  error: "Failed",
  stopped: "Stopped",
};

export function stateLabel(state: string): string {
  return STATE_LABELS[state] ?? state.replace(/_/g, " ");
}

export interface ExplainedError {
  /** What happened and what to do, in plain words. */
  summary: string;
  /** The original message, when it says more than the summary. */
  detail: string | null;
}

// AWS errors (and the like): the original message stays as detail.
const KNOWN: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/TargetNotConnected/i, () => "The bastion isn't reachable through SSM: it may be stopped, or its SSM agent is offline."],
  [
    /AccessDenied|not authorized to perform/i,
    () => "Your AWS role isn't allowed to open this tunnel. Check that the profile has SSM access to the bastion.",
  ],
  [/InvalidInstanceId|InvalidTarget/i, () => "The bastion instance wasn't found. Check its ID and region."],
  [/config profile \(([^)]+)\) could not be found/i, (m) => `The AWS profile "${m[1]}" isn't in your AWS config.`],
  // The AWS CLI's own message: matching "session-manager-plugin" anywhere also
  // caught every error naming the plugin's command, e.g. when it exits.
  [/SessionManagerPlugin is not found/i, () => "The AWS Session Manager plugin isn't installed."],
  [
    /Command '?\['session-manager-plugin'.*returned non-zero exit status (-?\d+)/i,
    (m) => `The SSM session closed (the Session Manager plugin stopped with code ${m[1]}).`,
  ],
  [
    /Token has expired|refresh failed|ExpiredToken|UnrecognizedClient/i,
    () => "Your AWS session expired. Log in to reconnect.",
  ],
  [
    /Could not connect to the endpoint|EndpointConnectionError|getaddrinfo|Name or service not known|timed out/i,
    () => "Can't reach AWS. Check your internet connection or VPN.",
  ],
  [
    /address already in use|Only one usage of each socket address|EADDRINUSE|10048/i,
    () => "Its local port is already used by another program.",
  ],
];

// The tunnel loop's own messages: the summary says all they do, so no detail.
const OWN: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/Failed to connect after (\d+) attempts/i, (m) => `Couldn't connect after ${m[1]} tries.`],
  [/Gave up waiting for AWS token refresh/i, () => "Stopped waiting for an AWS login after 30 minutes."],
  [/^Session ended$/i, () => "The SSM session ended."],
  [/SSM exited with code (-?\d+)/i, (m) => `The SSM session closed unexpectedly (code ${m[1]}).`],
];

// "An error occurred (Throttling) when calling the StartSession operation: Rate exceeded"
const AWS_PREFIX = /^An error occurred \(([^)]+)\) when calling the \w+ operation:\s*/i;

export function explainError(raw: string | null | undefined): ExplainedError | null {
  const text = raw?.trim();
  if (!text) return null;
  for (const [pattern, describe] of OWN) {
    const match = text.match(pattern);
    if (match) return { summary: describe(match), detail: null };
  }
  for (const [pattern, describe] of KNOWN) {
    const match = text.match(pattern);
    if (match) return { summary: describe(match), detail: text };
  }
  const stripped = text.replace(AWS_PREFIX, "");
  return { summary: stripped, detail: stripped === text ? null : text };
}
