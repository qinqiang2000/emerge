import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "@/i18n";
import { useT } from "@/i18n/useT";

function Probe() {
  const t = useT();
  return <span>{t("auth.login_title")}</span>;
}

describe("i18n", () => {
  it("renders a known catalog key", () => {
    render(<Probe />);
    expect(screen.getByText("Sign in to emerge")).toBeInTheDocument();
  });

  it("falls back to the key when missing", () => {
    function Bad() {
      const t = useT();
      return <span>{t("does.not.exist")}</span>;
    }
    render(<Bad />);
    expect(screen.getByText("does.not.exist")).toBeInTheDocument();
  });
});
