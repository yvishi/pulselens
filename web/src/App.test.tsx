import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { App } from "./App";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("App", () => {
  it("renders the home page with the three tasks", () => {
    renderAt("/");
    const tasks = within(screen.getByRole("navigation", { name: "Pages" })).getAllByRole("link");
    expect(tasks.map((l) => l.querySelector("h2")?.textContent)).toEqual([
      "Start a verification",
      "Review verifications",
      "Record test sessions",
    ]);
    expect(tasks.map((l) => l.getAttribute("href"))).toEqual(["/console", "/console", "/lab"]);
  });

  it("shows the main page links, with the current page marked", () => {
    renderAt("/");
    const nav = screen.getByRole("navigation", { name: "Main" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual(["Home", "Verifications", "Lab recording"]);
    expect(within(nav).getByRole("link", { name: "Home" }).getAttribute("aria-current")).toBe("page");
  });

  it("an unknown address offers the way home", () => {
    renderAt("/nowhere");
    expect(screen.getByRole("heading", { name: "This page does not exist" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go to the home page" }).getAttribute("href")).toBe("/");
  });
});
