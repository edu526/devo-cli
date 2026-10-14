import { describe, it, expect } from "vitest";
import {
  validate,
  databaseSchema,
  instanceSchema,
  hostSchema,
  profileSchema,
  regionFromHost,
  ssoSessionSchema,
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
  const db = { name: "db", bastion: "i-0942ab24eff8666c3", host: "h.local", port: 5432, region: "us-east-1" };

  it("coerces port string to number", () => {
    const r = validate(databaseSchema, { ...db, port: "5432" });
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.port).toBe(5432);
      expect(typeof r.data.port).toBe("number");
    }
  });
  it("rejects out-of-range port", () => {
    expect(validate(databaseSchema, { ...db, port: 70000 }).success).toBe(false);
  });
  it("rejects invalid name characters", () => {
    expect(validate(databaseSchema, { ...db, name: "bad name!" }).success).toBe(false);
  });
  it("needs an instance ID as bastion, not a name", () => {
    const r = validate(databaseSchema, { ...db, bastion: "prod-bastion" });
    expect(r.success).toBe(false);
    if (!r.success) expect(r.errors.bastion).toContain("instance ID");
    expect(validate(databaseSchema, { ...db, bastion: "mi-0123456789abcdef0" }).success).toBe(true);
  });
  it("ignores the local address Devo assigned (editing used to fail on 127.0.0.2)", () => {
    const r = validate(databaseSchema, { ...db, local_address: "127.0.0.2" });
    expect(r.success).toBe(true);
    if (r.success) expect("local_address" in r.data).toBe(false);
  });
});

describe("regionFromHost", () => {
  it("reads the region of an RDS endpoint", () => {
    expect(regionFromHost("mydb.cluster-abc123.us-east-1.rds.amazonaws.com")).toBe("us-east-1");
    expect(regionFromHost("db.xyz.eu-central-1.rds.amazonaws.com")).toBe("eu-central-1");
    expect(regionFromHost("db.xyz.us-gov-west-1.rds.amazonaws.com")).toBe("us-gov-west-1");
  });
  it("has none for global databases or other hosts", () => {
    expect(regionFromHost("epic-dev.global-gywzlzqizajw.global.rds.amazonaws.com")).toBeNull();
    expect(regionFromHost("10.0.0.5")).toBeNull();
    expect(regionFromHost("db.internal")).toBeNull();
  });
});

describe("profileSchema", () => {
  const valid = {
    name: "newdev",
    sso_session: "my-sso",
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
    const r = validate(profileSchema, { ...valid, region: "us east 1" });
    expect(r.success).toBe(false);
  });

  it("rejects an empty profile name", () => {
    const r = validate(profileSchema, { ...valid, name: "" });
    expect(r.success).toBe(false);
  });
});

describe("ssoSessionSchema", () => {
  const valid = {
    name: "my-company",
    sso_start_url: "https://example.awsapps.com/start",
    sso_region: "us-east-1",
  };

  it("accepts a well-formed session", () => {
    expect(validate(ssoSessionSchema, valid).success).toBe(true);
  });

  it("rejects a start URL that is not a valid URL", () => {
    const r = validate(ssoSessionSchema, { ...valid, sso_start_url: "not a url" });
    expect(r.success).toBe(false);
  });

  it("rejects a region not shaped like us-east-1", () => {
    const r = validate(ssoSessionSchema, { ...valid, sso_region: "us east 1" });
    expect(r.success).toBe(false);
  });
});
