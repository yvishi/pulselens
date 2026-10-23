import { describe, expect, it } from "vitest";
import { langFor, strings, t, type Lang } from "./strings";

const LANGS: Lang[] = ["en", "hi"];

describe("customer strings", () => {
  it("every key exists in both languages, and none is empty", () => {
    const keys = Object.keys(strings.en).sort();
    for (const lang of LANGS) {
      expect(Object.keys(strings[lang]).sort()).toEqual(keys);
      for (const k of keys) expect(strings[lang][k as keyof typeof strings.en].trim(), `${lang}:${k}`).not.toBe("");
    }
  });

  it("Hindi is written in Devanagari, not copied from English", () => {
    for (const k of Object.keys(strings.en) as (keyof typeof strings.en)[]) {
      if (k === "lang.en" || k === "lang.hi") continue;
      expect(strings.hi[k], k).toMatch(/[ऀ-ॿ]/);
    }
  });

  it("t() reads the chosen language", () => {
    expect(t("consent.start", "en")).toBe("Start");
    expect(t("consent.start", "hi")).not.toBe("Start");
  });

  it("the language follows navigator.language: hi* is Hindi, anything else English", () => {
    expect(langFor("hi")).toBe("hi");
    expect(langFor("hi-IN")).toBe("hi");
    expect(langFor("en-IN")).toBe("en");
    expect(langFor("")).toBe("en");
    expect(langFor(undefined)).toBe("en");
  });

  it("no string mentions a score or an outcome", () => {
    for (const lang of LANGS) {
      for (const v of Object.values(strings[lang])) expect(v).not.toMatch(/score|PASS|risk|family|outcome/i);
    }
  });
});
