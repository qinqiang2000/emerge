import { MoreVertical } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { useT } from "@/i18n/useT";
import { useStudio } from "@/stores/studio";

// Dogfood follow-up #3: editing the field's textbox IS the value-correction
// path. This menu only carries issue types that can't be expressed as a
// value-fix — `wrong_value` is intentionally absent so the dual-affordance
// the dogfood walk complained about doesn't sneak back in via the menu.
const ISSUE_TYPES = [
  "missing_field",
  "extra_field",
  "wrong_entity_count",
  "other",
] as const;

export function FlagFieldMenu({
  projectId,
  entityIndex,
  fieldName,
}: {
  projectId: number;
  entityIndex: number;
  fieldName: string;
}) {
  const t = useT();
  const issueId = useId();
  const commentId = useId();
  const [open, setOpen] = useState(false);
  const [issueType, setIssueType] = useState<string>("missing_field");
  const [comment, setComment] = useState("");
  const saving = useStudio((s) => s.saving);
  const flagField = useStudio((s) => s.flagField);

  async function onFlag() {
    await flagField({ projectId, entityIndex, fieldName, issueType, comment });
    setOpen(false);
  }

  return (
    <>
      <button
        type="button"
        aria-label={t("studio.flag.trigger_aria", { field: fieldName })}
        onClick={() => setOpen(true)}
        className="text-fg-muted hover:text-fg-primary"
      >
        <MoreVertical size={14} />
      </button>
      {open ? (
        <Dialog
          open={open}
          onOpenChange={setOpen}
          title={t("studio.flag.dialog_title")}
        >
          <div className="space-y-3 text-sm">
            <p className="text-xs text-fg-muted">
              {t("studio.flag.dialog_hint")}
            </p>
            <label htmlFor={issueId} className="flex flex-col gap-1 text-xs">
              <span className="text-fg-muted">
                {t("studio.flag.issue_type_label")}
              </span>
              <select
                id={issueId}
                value={issueType}
                onChange={(e) => setIssueType(e.target.value)}
                className="rounded-md border border-border-default bg-bg-surface px-2 py-1 text-fg-primary"
              >
                {ISSUE_TYPES.map((kind) => (
                  <option key={kind} value={kind}>
                    {t(`studio.flag.issue_type.${kind}`)}
                  </option>
                ))}
              </select>
            </label>
            <label htmlFor={commentId} className="flex flex-col gap-1 text-xs">
              <span className="text-fg-muted">
                {t("studio.flag.comment_label")}
              </span>
              <Input
                id={commentId}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setOpen(false)}>
                {t("studio.flag.cancel_button")}
              </Button>
              <Button onClick={() => void onFlag()} disabled={saving}>
                {t("studio.flag.flag_button")}
              </Button>
            </div>
          </div>
        </Dialog>
      ) : null}
    </>
  );
}
