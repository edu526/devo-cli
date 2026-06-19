import { describe, it, expect } from "vitest";
import {
  validate,
  databaseSchema,
  instanceSchema,
  hostSchema,
  profileSchema,
} from "../forms";

describe("validate()", () => {
  it("returns typed data on success", () => {
    const r = validate(hostSchema, { ip: "192.168.1.1", hostname: "box.local" });
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.ip).toBe("192.168.1.1");
    }
  });

  it("returns a flat errors map keyed by field", () => {
    const r = validate(hostSchema, { ip: "not-an-ip", hostname: "" });
    expect(r.success).toBe(false);
    if (!r.success) {
      expect(r.errors.ip).toBeDefined();
      expect(r.errors.hostname).toBeDefined();
    }
  });
});

describe("hostSchema", () => {
  it("rejects invalid IPv4", () => {
    const r = validate(hostSchema, { ip: "999.0.0.1", hostname: "x" });
    expect(r.success).toBe(false);
  });
  it("accepts loopback", () => {
    const r = validate(hostSchema, { ip: "127.0.0.1", hostname: "localhost" });
    expect(r.success).toBe(true);
  });
});

describe("instanceSchema", () => {
  it("requires an i- prefix on instance_id", () => {
    const r = validate(instanceSchema, {
      name: "p",
      instance_id: "abc123",
      region: "us-east-1",
    });
    expect(r.success).toBe(false);
  });
  it("accepts a real i- id", () => {
    const r = validate(instanceSchema, {
      name: "p",
      instance_id: "i-0abc123def456789a",
      region: "us-east-1",
    });
    expect(r.success).toBe(true);
  });
});

describe("databaseSchema", () => {
  it("coerces port string to number", () => {
    const r = validate(databaseSchema, {
      name: "db",
      bastion: "b",
      host: "h.local",
      port: "5432",
      region: "us-east-1",
    });
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.port).toBe(5432);
      expect(typeof r.data.port).toBe("number");
    }
  });
  it("rejects out-of-range port", () => {
    const r = validate(databaseSchema, {
      name: "db",
      bastion: "b",
      host: "h.local",
      port: 70000,
      region: "us-east-1",
    });
    expect(r.success).toBe(false);
  });
  it("rejects invalid name characters", () => {
    const r = validate(databaseSchema, {
      name: "bad name!",
      bastion: "b",
      host: "h.local",
      port: 5432,
      region: "us-east-1",
    });
    expect(r.success).toBe(false);
  });
});

describe("profileSchema", () => {
  const valid = {
    name: "newdev",
    sso_start_url: "https://example.awsapps.com/start",
    sso_region: "us-east-1",
    sso_account_id: "123456789012",
    sso_role_name: "ReadOnlyRole",
    region: "us-east-1",
  };

  it("accepts a well-formed profile", () => {
    expect(validate(profileSchema, valid).success).toBe(true);
  });

  it("rejects a non-12-digit account id", () => {
    const r = validate(profileSchema, { ...valid, sso_account_id: "12345" });
    expect(r.success).toBe(false);
  });

  it("rejects a region not shaped like us-east-1", () => {
    const r = validate(profileSchema, { ...valid, sso_region: "us east 1" });
    expect(r.success).toBe(false);
  });

  it("rejects a start URL that is not a valid URL", () => {
    const r = validate(profileSchema, { ...valid, sso_start_url: "not a url" });
    expect(r.success).toBe(false);
  });
});
