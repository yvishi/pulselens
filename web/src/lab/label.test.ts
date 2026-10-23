import { afterEach, describe, expect, it } from "vitest";
import { EMPTY_FORM, loadLastForm, saveLastForm, validateLabel, type LabelForm } from "./label";

const GOOD: LabelForm = {
  person: "P01", device: "D02", light: "dim", kind: "genuine", tool: "", set: "B", consent_ref: "CF-2026-014",
};

describe("validateLabel", () => {
  it("accepts a genuine recording and sets tool to null", () => {
    const r = validateLabel({ ...GOOD, tool: "ignored" });
    expect(r.errors).toBeNull();
    expect(r.label).toEqual({ ...GOOD, tool: null });
  });

  it("trims and upper-cases the codes", () => {
    const r = validateLabel({ ...GOOD, person: " p07 ", device: "d11", consent_ref: "  CF-1  " });
    expect(r.label).toMatchObject({ person: "P07", device: "D11", consent_ref: "CF-1" });
  });

  it.each(["", "P1", "P001", "X01", "Priya"])("rejects person %j", (person) => {
    expect(validateLabel({ ...GOOD, person }).errors).toHaveProperty("person");
  });

  it.each(["", "D1", "P01", "D123"])("rejects device %j", (device) => {
    expect(validateLabel({ ...GOOD, device }).errors).toHaveProperty("device");
  });

  it("requires a consent reference", () => {
    const r = validateLabel({ ...GOOD, consent_ref: "   " });
    expect(r.label).toBeNull();
    expect(Object.keys(r.errors ?? {})).toEqual(["consent_ref"]);
  });

  it("requires a tool unless the kind is genuine", () => {
    expect(validateLabel({ ...GOOD, kind: "replay_screen", tool: " " }).errors).toHaveProperty("tool");
    expect(validateLabel({ ...GOOD, kind: "replay_screen", tool: " phone_screen " }).label?.tool).toBe("phone_screen");
  });

  it("rejects values outside the contract's unions", () => {
    const bad = { ...GOOD, light: "dark", kind: "mask", tool: "x", set: "C" } as unknown as LabelForm;
    expect(Object.keys(validateLabel(bad).errors ?? {}).sort()).toEqual(["kind", "light", "set"]);
  });
});

describe("last-used settings", () => {
  afterEach(() => localStorage.clear());

  it("round-trips through storage", () => {
    saveLastForm(GOOD);
    expect(loadLastForm()).toEqual(GOOD);
  });

  it("falls back to the empty form on garbage", () => {
    localStorage.setItem("pulselens.lab.lastLabel", "{not json");
    expect(loadLastForm()).toEqual(EMPTY_FORM);
    localStorage.setItem("pulselens.lab.lastLabel", JSON.stringify({ person: "P03", light: "neon" }));
    expect(loadLastForm()).toEqual({ ...EMPTY_FORM, person: "P03" });
  });
});
