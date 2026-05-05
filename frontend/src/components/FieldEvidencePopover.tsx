import { Quote } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useT } from "@/i18n/useT";
import {
  EVIDENCE_ALLOWED_KEYS,
  type ConfidenceVerdict,
  type FieldEvidence,
  type PerFieldEvidence,
} from "@/types/studio";

function pickAllowedKeys(cell: unknown): FieldEvidence | null {
  if (cell === null || typeof cell !== "object") return null;
  const raw = cell as Record<string, unknown>;
  const safe: FieldEvidence = {};
  let hasAllowed = false;
  let hadForbidden = false;
  for (const key of Object.keys(raw)) {
    if ((EVIDENCE_ALLOWED_KEYS as ReadonlyArray<string>).includes(key)) {
      const value = raw[key];
      if (value === null || value === undefined) continue;
      // Type-narrow to the FieldEvidence shape; defensive against backend
      // shape drift. Spec §3.2 keeps every allowed key primitive.
      (safe as Record<string, unknown>)[key] = value;
      hasAllowed = true;
    } else {
      hadForbidden = true;
    }
  }
  if (hadForbidden) {
    console.warn(
      `[FieldEvidencePopover] dropped forbidden/unknown evidence keys; allow-list is ${EVIDENCE_ALLOWED_KEYS.join(
        ", ",
      )} (spec §3.2 — no bbox/coordinates/region/polygon/span)`,
    );
  }
  return hasAllowed ? safe : null;
}

export function FieldEvidencePopover({
  entityIndex,
  fieldName,
  evidenceMap,
}: {
  entityIndex: number;
  fieldName: string;
  evidenceMap: PerFieldEvidence | null | undefined;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLSpanElement | null>(null);

  const cell = evidenceMap?.[String(entityIndex)]?.[fieldName];
  const safe = cell ? pickAllowedKeys(cell) : null;

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  if (safe === null) return null;

  return (
    <span ref={wrapperRef} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={t("studio.evidence.show_button_aria")}
        className="inline-flex items-center rounded-sm border border-border-default bg-bg-elevated px-1.5 py-0.5 text-xs text-fg-muted hover:text-fg-primary"
      >
        <Quote size={12} aria-hidden="true" />
      </button>
      {open ? (
        <div
          role="dialog"
          aria-label={t("studio.evidence.popover_title")}
          className="absolute left-0 top-full z-10 mt-1 w-72 space-y-2 rounded-md border border-border-default bg-bg-surface p-3 text-sm text-fg-primary shadow-lg"
        >
          <p className="text-xs uppercase tracking-wide text-fg-muted">
            {t("studio.evidence.popover_title")}
          </p>
          {safe.page !== undefined ? (
            <p className="text-xs text-fg-muted">
              {t("studio.evidence.page_label", { page: safe.page })}
            </p>
          ) : null}
          {safe.quote ? (
            <blockquote className="border-l-2 border-border-strong pl-2 text-fg-primary">
              {safe.quote}
            </blockquote>
          ) : null}
          {safe.rationale ? (
            <div>
              <p className="text-xs uppercase tracking-wide text-fg-muted">
                {t("studio.evidence.rationale_label")}
              </p>
              <p className="text-fg-primary">{safe.rationale}</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </span>
  );
}

export function ConfidenceChip({
  verdict,
}: {
  verdict: ConfidenceVerdict | null | undefined;
}) {
  const t = useT();
  if (verdict === "up" || verdict === undefined || verdict === null) {
    return null;
  }
  if (verdict === "uncertain") {
    return (
      <span
        data-testid="confidence-chip"
        className="rounded-sm bg-bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-fg-muted"
      >
        {t("studio.confidence.uncertain")}
      </span>
    );
  }
  if (verdict === "down") {
    return (
      <span
        data-testid="confidence-chip"
        className="rounded-sm border border-status-warning px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-status-warning"
      >
        {t("studio.confidence.needs_review")}
      </span>
    );
  }
  return null;
}
