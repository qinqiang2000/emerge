import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "@/components/ui/Button";

describe("Button", () => {
  it("renders text content", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });

  it("does not contain raw bg-gray classes (token enforcement)", () => {
    const { container } = render(<Button>Hi</Button>);
    expect(container.innerHTML).not.toMatch(
      /bg-gray-|bg-white\b|bg-black\b|text-white\b|text-black\b/,
    );
  });
});
