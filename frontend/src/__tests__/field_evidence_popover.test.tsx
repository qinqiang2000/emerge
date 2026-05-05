import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ConfidenceChip,
  FieldEvidencePopover,
} from "@/components/FieldEvidencePopover";
import type { PerFieldEvidence } from "@/types/studio";

const TRIGGER_LABEL = /show evidence/i;

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FieldEvidencePopover — happy path", () => {
  const evidenceMap: PerFieldEvidence = {
    "0": {
      total: {
        page: 1,
        quote: "Total ¥1,234",
        rationale: "Used the tax-included total line.",
      },
    },
  };

  it("opens the panel and renders page, quote, and rationale on click", () => {
    render(
      <FieldEvidencePopover
        entityIndex={0}
        fieldName="total"
        evidenceMap={evidenceMap}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: TRIGGER_LABEL }));
    expect(screen.getByText(/page 1/i)).toBeInTheDocument();
    expect(screen.getByText("Total ¥1,234")).toBeInTheDocument();
    expect(
      screen.getByText("Used the tax-included total line."),
    ).toBeInTheDocument();
  });
});

describe("FieldEvidencePopover — rationale-only path", () => {
  it("renders rationale alone without an empty Page line or empty quote", () => {
    const evidenceMap: PerFieldEvidence = {
      "0": {
        total: {
          rationale: "Inferred from header context only.",
        },
      },
    };
    render(
      <FieldEvidencePopover
        entityIndex={0}
        fieldName="total"
        evidenceMap={evidenceMap}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: TRIGGER_LABEL }));
    expect(
      screen.getByText("Inferred from header context only."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/page/i)).not.toBeInTheDocument();
    // The quote row uses a <blockquote>; if no quote, no blockquote is mounted.
    expect(screen.queryByRole("blockquote")).not.toBeInTheDocument();
  });
});

describe("FieldEvidencePopover — no-evidence path", () => {
  it("does not render any trigger button when the field has no evidence cell", () => {
    render(
      <FieldEvidencePopover
        entityIndex={0}
        fieldName="total"
        evidenceMap={{ "0": { other: { page: 1, quote: "x" } } }}
      />,
    );
    expect(
      screen.queryByRole("button", { name: TRIGGER_LABEL }),
    ).not.toBeInTheDocument();
  });

  it("does not render a trigger button when the entity has no evidence at all", () => {
    render(
      <FieldEvidencePopover
        entityIndex={0}
        fieldName="total"
        evidenceMap={{}}
      />,
    );
    expect(
      screen.queryByRole("button", { name: TRIGGER_LABEL }),
    ).not.toBeInTheDocument();
  });

  it("does not render a trigger button when evidenceMap is null/undefined", () => {
    render(
      <FieldEvidencePopover
        entityIndex={0}
        fieldName="total"
        evidenceMap={null}
      />,
    );
    expect(
      screen.queryByRole("button", { name: TRIGGER_LABEL }),
    ).not.toBeInTheDocument();
  });

  it("does not render a trigger when the cell exists but has no allow-listed keys", () => {
    // Backend allow-list strips forbidden keys at write time, but a partially
    // sanitised payload could in theory still arrive with an empty cell.
    // No allow-listed keys → button hidden.
    render(
      <FieldEvidencePopover
        entityIndex={0}
        fieldName="total"
        evidenceMap={{ "0": { total: {} } }}
      />,
    );
    expect(
      screen.queryByRole("button", { name: TRIGGER_LABEL }),
    ).not.toBeInTheDocument();
  });
});

describe("FieldEvidencePopover — dismissal", () => {
  const evidenceMap: PerFieldEvidence = {
    "0": {
      total: { page: 1, quote: "Total ¥1,234", rationale: "tax-included" },
    },
  };

  it("toggles closed when the trigger is clicked again", () => {
    render(
      <FieldEvidencePopover
        entityIndex={0}
        fieldName="total"
        evidenceMap={evidenceMap}
      />,
    );
    const trigger = screen.getByRole("button", { name: TRIGGER_LABEL });
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(trigger);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes when Escape is pressed", () => {
    render(
      <FieldEvidencePopover
        entityIndex={0}
        fieldName="total"
        evidenceMap={evidenceMap}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: TRIGGER_LABEL }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on a mousedown outside the popover", () => {
    render(
      <div>
        <FieldEvidencePopover
          entityIndex={0}
          fieldName="total"
          evidenceMap={evidenceMap}
        />
        <button data-testid="outside" type="button">
          outside
        </button>
      </div>,
    );
    fireEvent.click(screen.getByRole("button", { name: TRIGGER_LABEL }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("FieldEvidencePopover — bbox-leak defense", () => {
  it("never renders coordinate keys even if the backend leaks them", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const evidenceMap = {
      "0": {
        total: {
          page: 1,
          quote: "Total ¥1,234",
          rationale: "tax-included",
          // Forbidden visual-localisation keys — must never reach the DOM:
          bbox: [10, 20, 100, 50],
          coordinates: { x: 10, y: 20 },
          polygon: [
            [0, 0],
            [1, 0],
            [1, 1],
          ],
          region: "page-1-line-3",
          span: [120, 132],
        },
      },
    } as unknown as PerFieldEvidence;

    render(
      <FieldEvidencePopover
        entityIndex={0}
        fieldName="total"
        evidenceMap={evidenceMap}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: TRIGGER_LABEL }));

    const panel = screen.getByRole("dialog");
    for (const forbidden of [
      "bbox",
      "coordinates",
      "polygon",
      "region",
      "span",
      "10",
      "20",
      "100",
      "50",
      "page-1-line-3",
    ]) {
      expect(panel.textContent ?? "").not.toContain(forbidden);
    }
    expect(warn).toHaveBeenCalled();
    expect(warn.mock.calls.some((call) => /bbox|forbidden/i.test(String(call[0])))).toBe(
      true,
    );
  });
});

describe("ConfidenceChip", () => {
  it("renders nothing for `up` (silent)", () => {
    const { container } = render(<ConfidenceChip verdict="up" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a muted chip for `uncertain`", () => {
    render(<ConfidenceChip verdict="uncertain" />);
    const chip = screen.getByTestId("confidence-chip");
    expect(chip).toHaveTextContent(/uncertain/i);
    expect(chip.className).toMatch(/bg-bg-muted/);
  });

  it("renders a status-warning chip for `down`", () => {
    render(<ConfidenceChip verdict="down" />);
    const chip = screen.getByTestId("confidence-chip");
    expect(chip).toHaveTextContent(/needs review/i);
    expect(chip.className).toMatch(/text-status-warning|bg-status-warning/);
  });

  it("renders nothing when verdict is undefined or unknown", () => {
    const { container, rerender } = render(<ConfidenceChip verdict={undefined} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ConfidenceChip verdict={"weird" as unknown as "up"} />);
    expect(container).toBeEmptyDOMElement();
  });
});
