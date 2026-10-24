import { describe, expect, it } from "vitest";
import { QUESTION_POOL, checksNote, pickQuestions } from "./AgentQuestions";

function seeded(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const [HEAD, TAIL] = QUESTION_POOL[3]!.split("####") as [string, string];
const fromPool = (q: string) =>
  QUESTION_POOL.some((t) =>
    t.includes("####") ? q.startsWith(HEAD) && q.endsWith(TAIL) && /^\d{4}$/.test(q.slice(HEAD.length, q.length - TAIL.length)) : t === q,
  );

describe("pickQuestions", () => {
  it("picks 3 distinct prompts from the pool, with 4 random digits in the digits prompt", () => {
    for (let seed = 1; seed <= 200; seed++) {
      const qs = pickQuestions(seeded(seed));
      expect(qs).toHaveLength(3);
      expect(new Set(qs).size).toBe(3);
      qs.forEach((q) => {
        expect(fromPool(q)).toBe(true);
        expect(q).not.toContain("####");
      });
    }
  });

  it("is deterministic for a seeded rng", () => {
    expect(pickQuestions(seeded(7))).toEqual(pickQuestions(seeded(7)));
  });

  it("with the default rng always returns 3 distinct prompts", () => {
    for (let i = 0; i < 200; i++) expect(new Set(pickQuestions()).size).toBe(3);
  });
});

describe("checksNote", () => {
  it("lists each prompt with done or not done", () => {
    expect(checksNote(["A.", "B."], [true, false])).toBe("Live checks: A. done; B. not done");
  });
});
