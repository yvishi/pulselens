import { useId } from "react";

export const QUESTION_POOL: string[] = [
  "Ask them to wave a hand slowly in front of their face.",
  "Ask them to turn their head fully to one side and show their ear.",
  "Ask them to hold their ID card next to their face.",
  "Ask them to read these digits aloud: ####.",
  "Ask them to touch their nose, then their ear.",
];

const SHOWN = 3;

/** A random number in [0, 1) from the browser's secure generator. */
function cryptoRandom(): number {
  const buf = new Uint32Array(1);
  crypto.getRandomValues(buf);
  return buf[0] / 4294967296;
}

/** Three distinct prompts in random order. The digits prompt gets 4 fresh digits. */
export function pickQuestions(rng: () => number = cryptoRandom): string[] {
  const pool = [...QUESTION_POOL];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, SHOWN).map((q) => q.replace("####", () => Array.from({ length: 4 }, () => Math.floor(rng() * 10)).join("")));
}

/** The tick summary saved with the agent's decision note. */
export function checksNote(questions: string[], done: boolean[]): string {
  return "Live checks: " + questions.map((q, i) => `${q} ${done[i] ? "done" : "not done"}`).join("; ");
}

interface Props {
  questions: string[];
  done: boolean[];
  onToggle: (index: number) => void;
}

/** Live prompts the agent asks on the call, with a tick for each one asked. */
export function AgentQuestions({ questions, done, onToggle }: Props) {
  const id = useId();
  return (
    <section className="card agent-questions" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>Live questions to ask</h2>
      <p className="muted">Ask these on the call. A face swap often breaks when something covers the face or the head turns far.</p>
      <ul>
        {questions.map((q, i) => (
          <li key={q}>
            <label>
              <input type="checkbox" checked={Boolean(done[i])} onChange={() => onToggle(i)} /> {q}
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}
