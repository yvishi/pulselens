import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders the home page with three links", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    const links = screen.getAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual([
      "Customer demo (from the console)",
      "Lab recording",
      "Agent console",
    ]);
  });
});
