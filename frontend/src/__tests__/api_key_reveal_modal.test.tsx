import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiKeyRevealModal } from "@/components/ApiKeyRevealModal";

const SAMPLE = {
  id: 9,
  prefix: "ek_abc",
  name: "default",
  key: "ek_abcdefghijklmnopqrstuvwxyz",
};

afterEach(() => {
  vi.restoreAllMocks();
});

function renderModal(props?: Partial<Parameters<typeof ApiKeyRevealModal>[0]>) {
  const onConfirmDismiss = props?.onConfirmDismiss ?? vi.fn();
  render(
    <ApiKeyRevealModal
      open={props?.open ?? true}
      apiKey={props?.apiKey ?? SAMPLE}
      onConfirmDismiss={onConfirmDismiss}
    />,
  );
  return { onConfirmDismiss };
}

describe("ApiKeyRevealModal", () => {
  it("renders the plaintext key inside a dialog with the right role", () => {
    renderModal();
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(SAMPLE.key)).toBeInTheDocument();
  });

  it("dismiss button is disabled until the ack checkbox is checked", () => {
    const { onConfirmDismiss } = renderModal();
    const dismiss = screen.getByRole("button", { name: /done|dismiss|close/i });
    expect(dismiss).toBeDisabled();

    fireEvent.click(screen.getByRole("checkbox", { name: /copied/i }));
    expect(dismiss).not.toBeDisabled();
    fireEvent.click(dismiss);
    expect(onConfirmDismiss).toHaveBeenCalledTimes(1);
  });

  it("Copy button writes the plaintext to clipboard", () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    renderModal();
    fireEvent.click(screen.getByRole("button", { name: /copy/i }));
    expect(writeText).toHaveBeenCalledWith(SAMPLE.key);
  });

  it("includes a strong shown-only-once warning", () => {
    renderModal();
    expect(
      screen.getByText(/save it in your secrets manager/i),
    ).toBeInTheDocument();
  });

  it("does not render anything when open=false", () => {
    renderModal({ open: false });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
