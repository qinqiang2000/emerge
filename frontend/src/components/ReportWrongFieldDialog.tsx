import { useEffect, useId, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { useT } from "@/i18n/useT";
import {
  buildPartialFeedback,
  fieldPathFor,
  type FeedbackCorrection,
  type PartialFeedbackPayload,
} from "@/lib/feedback";
import { useStudio } from "@/stores/studio";

// Studio-only dialog that mirrors the public partial-feedback contract
// (R8.6.b) so users learn the shape integrators send. In Lab the same
// correction is posted to /annotations — Lab has no API-key surface and
// must NOT route through /extract/.../feedback (R8.6 hard rule).

function parseCorrectValue(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function buildEquivalentPayload(args: {
  predictionId: number | null;
  entityIndex: number;
  fieldName: string;
  correctValue: unknown;
}): PartialFeedbackPayload | null {
  if (args.predictionId === null) return null;
  let path: string;
  try {
    path = fieldPathFor(args.entityIndex, args.fieldName);
  } catch {
    return null;
  }
  const correction: FeedbackCorrection = {
    entity_index: args.entityIndex,
    field_path: path,
    correct_value: args.correctValue,
  };
  try {
    return buildPartialFeedback({
      predictionId: args.predictionId,
      corrections: [correction],
    });
  } catch {
    return null;
  }
}

function valueToInputString(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

export function ReportWrongFieldDialog({
  open,
  onOpenChange,
  entityIndex,
  fieldName,
  currentValue,
  projectId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entityIndex: number;
  fieldName: string;
  currentValue: unknown;
  projectId: number;
}) {
  const t = useT();
  const valueId = useId();

  const doc = useStudio((s) => s.doc);
  const saving = useStudio((s) => s.saving);
  const reportWrong = useStudio((s) => s.reportWrong);

  const initial = valueToInputString(currentValue);
  const [correctedStr, setCorrectedStr] = useState(initial);

  // Reset the input when the dialog re-opens against a different field.
  useEffect(() => {
    if (open) setCorrectedStr(valueToInputString(currentValue));
  }, [open, currentValue]);

  const predictionId = doc?.latest_prediction?.id ?? null;

  const equivalent = useMemo(
    () =>
      buildEquivalentPayload({
        predictionId,
        entityIndex,
        fieldName,
        correctValue: parseCorrectValue(correctedStr),
      }),
    [predictionId, entityIndex, fieldName, correctedStr],
  );

  async function onSave() {
    await reportWrong({
      projectId,
      entityIndex,
      fieldName,
      correctValue: parseCorrectValue(correctedStr),
    });
    onOpenChange(false);
  }

  const fieldPath = (() => {
    try {
      return fieldPathFor(entityIndex, fieldName);
    } catch {
      return fieldName;
    }
  })();

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("studio.report_wrong.dialog_title")}
    >
      <div className="space-y-3 text-sm">
        <p className="text-xs text-fg-muted">
          {t("studio.report_wrong.dialog_hint")}
        </p>

        <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-fg-muted">
            {t("studio.report_wrong.entity_index_label")}
          </dt>
          <dd className="font-mono text-fg-primary">{entityIndex}</dd>
          <dt className="text-fg-muted">
            {t("studio.report_wrong.field_path_label")}
          </dt>
          <dd className="font-mono text-fg-primary">{fieldPath}</dd>
          <dt className="text-fg-muted">
            {t("studio.report_wrong.current_value_label")}
          </dt>
          <dd className="font-mono text-fg-primary">{initial || "—"}</dd>
        </dl>

        <div className="space-y-1">
          <label
            htmlFor={valueId}
            className="text-xs font-semibold text-fg-primary"
          >
            {t("studio.report_wrong.corrected_value_label")}
          </label>
          <Input
            id={valueId}
            value={correctedStr}
            onChange={(e) => setCorrectedStr(e.target.value)}
          />
        </div>

        {predictionId === null ? (
          <p role="alert" className="text-xs text-status-error">
            {t("studio.report_wrong.errors.no_prediction")}
          </p>
        ) : null}

        <details>
          <summary className="cursor-pointer text-xs font-semibold text-fg-primary">
            {t("studio.report_wrong.show_equivalent")}
          </summary>
          <pre
            data-testid="partial-feedback-equivalent"
            className="mt-2 overflow-x-auto rounded-sm border border-border-default bg-bg-muted p-2 font-mono text-xs text-fg-primary"
          >
            <code>
              {equivalent
                ? JSON.stringify(equivalent, null, 2)
                : "—"}
            </code>
          </pre>
        </details>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {t("studio.report_wrong.cancel_button")}
          </Button>
          <Button
            onClick={() => void onSave()}
            disabled={saving || predictionId === null}
          >
            {t("studio.report_wrong.save_button")}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
