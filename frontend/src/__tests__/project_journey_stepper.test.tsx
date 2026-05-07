import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProjectJourneyStepper } from "@/components/ProjectJourneyStepper";

describe("ProjectJourneyStepper", () => {
  it("renders the four-step reviewed examples journey", () => {
    render(
      <ProjectJourneyStepper
        hasDocuments
        hasDrafts
        reviewedDocs={2}
        hasImproveProposal={false}
        isPublished={false}
        canPublish={false}
        onExtract={vi.fn()}
        onReview={vi.fn()}
        onImprove={vi.fn()}
        onPublish={vi.fn()}
      />,
    );
    expect(screen.getByText("Extract drafts")).toBeInTheDocument();
    expect(screen.getByText("Review examples")).toBeInTheDocument();
    expect(screen.getByText("Improve extractor")).toBeInTheDocument();
    expect(screen.getByText("Publish API")).toBeInTheDocument();
  });

  it("disables Review examples until draft extractions exist", () => {
    render(
      <ProjectJourneyStepper
        hasDocuments
        hasDrafts={false}
        reviewedDocs={0}
        hasImproveProposal={false}
        isPublished={false}
        canPublish={false}
        onExtract={vi.fn()}
        onReview={vi.fn()}
        onImprove={vi.fn()}
        onPublish={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /review examples/i }),
    ).toBeDisabled();
  });

  it("calls the Improve extractor action when reviewed examples exist", () => {
    const onImprove = vi.fn();
    render(
      <ProjectJourneyStepper
        hasDocuments
        hasDrafts
        reviewedDocs={3}
        hasImproveProposal={false}
        isPublished={false}
        canPublish={false}
        onExtract={vi.fn()}
        onReview={vi.fn()}
        onImprove={onImprove}
        onPublish={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /improve extractor/i }));
    expect(onImprove).toHaveBeenCalledTimes(1);
  });

  it("disables Extract drafts until documents exist", () => {
    render(
      <ProjectJourneyStepper
        hasDocuments={false}
        hasDrafts={false}
        reviewedDocs={0}
        hasImproveProposal={false}
        isPublished={false}
        canPublish={false}
        onExtract={vi.fn()}
        onReview={vi.fn()}
        onImprove={vi.fn()}
        onPublish={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /extract drafts/i }),
    ).toBeDisabled();
  });

  it("calls the Review examples action when draft extractions exist", () => {
    const onReview = vi.fn();
    render(
      <ProjectJourneyStepper
        hasDocuments
        hasDrafts
        reviewedDocs={0}
        hasImproveProposal={false}
        isPublished={false}
        canPublish={false}
        onExtract={vi.fn()}
        onReview={onReview}
        onImprove={vi.fn()}
        onPublish={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /review examples/i }));
    expect(onReview).toHaveBeenCalledTimes(1);
  });

  it("disables Publish API until publishing is allowed or already published", () => {
    const { rerender } = render(
      <ProjectJourneyStepper
        hasDocuments
        hasDrafts
        reviewedDocs={2}
        hasImproveProposal={false}
        isPublished={false}
        canPublish={false}
        onExtract={vi.fn()}
        onReview={vi.fn()}
        onImprove={vi.fn()}
        onPublish={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /publish api/i })).toBeDisabled();

    rerender(
      <ProjectJourneyStepper
        hasDocuments
        hasDrafts
        reviewedDocs={2}
        hasImproveProposal={false}
        isPublished={false}
        canPublish
        onExtract={vi.fn()}
        onReview={vi.fn()}
        onImprove={vi.fn()}
        onPublish={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /publish api/i })).toBeEnabled();

    rerender(
      <ProjectJourneyStepper
        hasDocuments
        hasDrafts
        reviewedDocs={2}
        hasImproveProposal={false}
        isPublished
        canPublish={false}
        onExtract={vi.fn()}
        onReview={vi.fn()}
        onImprove={vi.fn()}
        onPublish={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /publish api/i })).toBeEnabled();
  });
});
