import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FeedbackTestForm } from "@/components/FeedbackTestForm";
import { api, EmergeError } from "@/lib/api";

afterEach(() => {
  vi.restoreAllMocks();
});

function setup() {
  // Each input must have an accessible name via label/aria-label, so we
  // just render the form and let getByLabelText / getByRole drive.
  return render(<FeedbackTestForm apiCode="japan-receipts" />);
}

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText(/api key/i), {
    target: { value: "ek_xyzABCDEFGHIJKLMNOPQRSTUVWXYZ" },
  });
  fireEvent.change(screen.getByLabelText(/request id/i), {
    target: { value: "42" },
  });
  fireEvent.change(screen.getByLabelText(/entity index/i), {
    target: { value: "0" },
  });
  fireEvent.change(screen.getByLabelText(/field path/i), {
    target: { value: "total" },
  });
  fireEvent.change(screen.getByLabelText(/correct value/i), {
    target: { value: "1234" },
  });
}

describe("FeedbackTestForm — submit flow", () => {
  it("POSTs to /extract/{api_code}/feedback with X-Api-Key header and payload shape", async () => {
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { counterexample_id: 88 } });

    setup();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /send test feedback/i }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    const [url, body, opts] = post.mock.calls[0]!;
    expect(url).toBe("/extract/japan-receipts/feedback");
    expect(body).toMatchObject({
      request_id: 42,
      corrections: [
        {
          entity_index: 0,
          field_path: "total",
          correct_value: 1234,
        },
      ],
    });
    expect(opts).toEqual(
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Api-Key": "ek_xyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        }),
      }),
    );
  });

  it("does not smuggle the session JWT onto the public-feedback POST", async () => {
    // The shared axios instance carries Authorization for authenticated
    // routes. Posts to the public /extract/{api_code}/feedback endpoint
    // must not bleed that session credential.
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { counterexample_id: 1 } });
    setup();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /send test feedback/i }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    const opts = post.mock.calls[0]![2] as
      | { headers?: Record<string, unknown> }
      | undefined;
    expect(opts?.headers).toBeDefined();
    // axios drops headers with value `undefined`. The presence of a
    // truthy Authorization here would be a JWT bleed.
    expect(opts?.headers?.Authorization ?? null).toBeFalsy();
  });

  it("parses numeric correct_value as JSON", async () => {
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { counterexample_id: 1 } });
    setup();
    fillRequiredFields();
    fireEvent.change(screen.getByLabelText(/correct value/i), {
      target: { value: "1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send test feedback/i }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0]![1]).toMatchObject({
      corrections: [expect.objectContaining({ correct_value: 1234 })],
    });
  });

  it("falls back to string when correct_value is not valid JSON", async () => {
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { counterexample_id: 1 } });
    setup();
    fillRequiredFields();
    fireEvent.change(screen.getByLabelText(/correct value/i), {
      target: { value: "hello world" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send test feedback/i }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0]![1]).toMatchObject({
      corrections: [expect.objectContaining({ correct_value: "hello world" })],
    });
  });

  it("includes optional comment, issue_type, and notes in the payload when provided", async () => {
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { counterexample_id: 1 } });
    setup();
    fillRequiredFields();
    fireEvent.change(screen.getByLabelText(/comment/i), {
      target: { value: "looked at the receipt twice" },
    });
    fireEvent.change(screen.getByLabelText(/notes/i), {
      target: { value: "from regression set" },
    });
    // The Select for issue_type — we simulate a controlled Select via
    // its accessible label; the default value should be wrong_value.
    fireEvent.click(screen.getByRole("button", { name: /send test feedback/i }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    const body = post.mock.calls[0]![1] as Record<string, unknown>;
    expect(body).toMatchObject({
      issue_type: "wrong_value",
      notes: "from regression set",
      corrections: [
        expect.objectContaining({ comment: "looked at the receipt twice" }),
      ],
    });
  });

  it("displays the returned counterexample_id on success and clears the API key field", async () => {
    vi.spyOn(api, "post").mockResolvedValue({
      data: { counterexample_id: 77 },
    });
    setup();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /send test feedback/i }));

    expect(await screen.findByText(/counterexample.*77/i)).toBeInTheDocument();
    // Plaintext key must be cleared on success — the field reverts to empty.
    const keyInput = screen.getByLabelText(/api key/i) as HTMLInputElement;
    expect(keyInput.value).toBe("");
  });

  it("shows a translated error message when the EmergeError envelope returns a known code", async () => {
    vi.spyOn(api, "post").mockRejectedValue(
      new EmergeError("UNAUTHORIZED", "missing X-Api-Key", 401),
    );
    setup();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /send test feedback/i }));
    expect(
      await screen.findByText(/please sign in/i),
    ).toBeInTheDocument();
  });
});

describe("FeedbackTestForm — transient API key state (security)", () => {
  it("does not persist the pasted key to localStorage", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    setup();
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "ek_secret_should_never_persist" },
    });
    for (const call of setItem.mock.calls) {
      expect(String(call[1] ?? "")).not.toContain("ek_secret_should_never_persist");
    }
  });

  it("clears the API key field when the form is unmounted and remounted", () => {
    const { unmount } = setup();
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "ek_remount_should_clear" },
    });
    expect(
      (screen.getByLabelText(/api key/i) as HTMLInputElement).value,
    ).toBe("ek_remount_should_clear");

    unmount();
    // Re-render fresh — the field comes back empty (proves no module-level
    // / store / localStorage retention of the key).
    setup();
    expect(
      (screen.getByLabelText(/api key/i) as HTMLInputElement).value,
    ).toBe("");
  });
});

describe("FeedbackTestForm — input validation", () => {
  it("shows a validation error when API key is empty and does not call the API", () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    setup();
    // Fill everything except the API key.
    fireEvent.change(screen.getByLabelText(/request id/i), {
      target: { value: "42" },
    });
    fireEvent.change(screen.getByLabelText(/entity index/i), {
      target: { value: "0" },
    });
    fireEvent.change(screen.getByLabelText(/field path/i), {
      target: { value: "total" },
    });
    fireEvent.change(screen.getByLabelText(/correct value/i), {
      target: { value: "1234" },
    });
    const submit = screen.getByRole("button", { name: /send test feedback/i });
    expect(submit).toBeDisabled();
    fireEvent.click(submit);
    expect(post).not.toHaveBeenCalled();
  });

  it("rejects a non-positive request_id at submit time without hitting the API", () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    setup();
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "ek_abc" },
    });
    fireEvent.change(screen.getByLabelText(/request id/i), {
      target: { value: "0" },
    });
    fireEvent.change(screen.getByLabelText(/entity index/i), {
      target: { value: "0" },
    });
    fireEvent.change(screen.getByLabelText(/field path/i), {
      target: { value: "total" },
    });
    fireEvent.change(screen.getByLabelText(/correct value/i), {
      target: { value: "1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send test feedback/i }));
    expect(post).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /request id must be a positive integer/i,
    );
  });

  it("shows an entity-index-specific error (not the request_id message) on bad entity_index", () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    setup();
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "ek_abc" },
    });
    fireEvent.change(screen.getByLabelText(/request id/i), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText(/entity index/i), {
      target: { value: "-1" },
    });
    fireEvent.change(screen.getByLabelText(/field path/i), {
      target: { value: "total" },
    });
    fireEvent.change(screen.getByLabelText(/correct value/i), {
      target: { value: "1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send test feedback/i }));
    expect(post).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /entity index must be a non-negative integer/i,
    );
  });
});
