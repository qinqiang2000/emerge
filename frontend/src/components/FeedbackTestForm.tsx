import { useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { useT } from "@/i18n/useT";
import { api, EmergeError, emergeErrorKey } from "@/lib/api";
import {
  FEEDBACK_ISSUE_TYPES,
  buildPartialFeedback,
  type FeedbackIssueType,
} from "@/lib/feedback";

// FeedbackTestForm renders an interactive form for the public partial-feedback
// shape and POSTs it to /extract/{api_code}/feedback with X-Api-Key.
//
// Security model (mirrors the R8.5 EVIDENCE_ALLOWED_KEYS pattern):
// - The plaintext API key lives in component state only.
// - It is never written to localStorage / Zustand / module scope.
// - It is cleared on successful submit and on unmount.

function parseCorrectValue(raw: string): unknown {
  // Try JSON first so users can express numbers, booleans, null, arrays,
  // and objects. Fall back to the raw string when JSON parsing fails.
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

export function FeedbackTestForm({ apiCode }: { apiCode: string }) {
  const t = useT();

  const keyId = useId();
  const requestId = useId();
  const entityId = useId();
  const fieldPathId = useId();
  const correctValueId = useId();
  const commentId = useId();
  const issueTypeId = useId();
  const notesId = useId();

  const [apiKey, setApiKey] = useState("");
  const [requestIdStr, setRequestIdStr] = useState("");
  const [entityIndexStr, setEntityIndexStr] = useState("0");
  const [fieldPath, setFieldPath] = useState("");
  const [correctValueStr, setCorrectValueStr] = useState("");
  const [comment, setComment] = useState("");
  const [issueType, setIssueType] = useState<FeedbackIssueType>("wrong_value");
  const [notes, setNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [successId, setSuccessId] = useState<number | null>(null);

  // Defense in depth: clear the plaintext key on unmount even if React would
  // GC the state anyway, so re-mount yields an empty input. The component
  // test pins this behavior.
  useEffect(() => {
    return () => {
      setApiKey("");
    };
  }, []);

  const canSubmit =
    apiKey.length > 0 &&
    requestIdStr.length > 0 &&
    fieldPath.length > 0 &&
    !submitting;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorKey(null);
    setSuccessId(null);

    const requestIdNum = Number(requestIdStr);
    if (!Number.isInteger(requestIdNum) || requestIdNum <= 0) {
      setErrorKey("feedback.errors.request_id_must_be_positive");
      return;
    }
    const entityIndexNum = Number(entityIndexStr);
    if (!Number.isInteger(entityIndexNum) || entityIndexNum < 0) {
      setErrorKey("feedback.errors.entity_index_must_be_non_negative");
      return;
    }

    let payload;
    try {
      payload = buildPartialFeedback({
        predictionId: requestIdNum,
        corrections: [
          {
            entity_index: entityIndexNum,
            field_path: fieldPath,
            correct_value: parseCorrectValue(correctValueStr),
            ...(comment ? { comment } : {}),
          },
        ],
        issueType,
        ...(notes ? { notes } : {}),
      });
    } catch {
      setErrorKey("feedback.errors.submit_failed");
      return;
    }

    setSubmitting(true);
    try {
      // The shared axios instance carries an Authorization JWT for
      // authenticated routes. The public /extract/{api_code}/feedback
      // endpoint authenticates via X-Api-Key only — explicitly drop the
      // JWT so we do not smuggle a session credential onto the public
      // boundary. axios v1 drops headers whose value is `undefined`.
      const resp = await api.post(
        `/extract/${apiCode}/feedback`,
        payload,
        {
          headers: {
            "X-Api-Key": apiKey,
            Authorization: undefined as unknown as string,
          },
        },
      );
      const id = (resp.data as { counterexample_id?: number })?.counterexample_id;
      setSuccessId(typeof id === "number" ? id : null);
      setApiKey("");
    } catch (err) {
      setErrorKey(
        err instanceof EmergeError
          ? emergeErrorKey(err)
          : "feedback.errors.submit_failed",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div className="space-y-1">
        <label htmlFor={keyId} className="text-xs font-semibold text-fg-primary">
          {t("feedback.key_label")}
        </label>
        <Input
          id={keyId}
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={t("feedback.key_placeholder")}
        />
        <p className="text-xs text-fg-muted">{t("feedback.key_helper")}</p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label
            htmlFor={requestId}
            className="text-xs font-semibold text-fg-primary"
          >
            {t("feedback.request_id_label")}
          </label>
          <Input
            id={requestId}
            inputMode="numeric"
            value={requestIdStr}
            onChange={(e) => setRequestIdStr(e.target.value)}
          />
          <p className="text-xs text-fg-muted">{t("feedback.request_id_helper")}</p>
        </div>
        <div className="space-y-1">
          <label
            htmlFor={entityId}
            className="text-xs font-semibold text-fg-primary"
          >
            {t("feedback.entity_index_label")}
          </label>
          <Input
            id={entityId}
            inputMode="numeric"
            value={entityIndexStr}
            onChange={(e) => setEntityIndexStr(e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-1">
        <label
          htmlFor={fieldPathId}
          className="text-xs font-semibold text-fg-primary"
        >
          {t("feedback.field_path_label")}
        </label>
        <Input
          id={fieldPathId}
          value={fieldPath}
          onChange={(e) => setFieldPath(e.target.value)}
          placeholder={t("feedback.field_path_placeholder")}
        />
      </div>

      <div className="space-y-1">
        <label
          htmlFor={correctValueId}
          className="text-xs font-semibold text-fg-primary"
        >
          {t("feedback.correct_value_label")}
        </label>
        <Input
          id={correctValueId}
          value={correctValueStr}
          onChange={(e) => setCorrectValueStr(e.target.value)}
        />
        <p className="text-xs text-fg-muted">{t("feedback.correct_value_helper")}</p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label
            htmlFor={commentId}
            className="text-xs font-semibold text-fg-primary"
          >
            {t("feedback.comment_label")}
          </label>
          <Input
            id={commentId}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <label
            htmlFor={issueTypeId}
            className="text-xs font-semibold text-fg-primary"
          >
            {t("feedback.issue_type_label")}
          </label>
          <select
            id={issueTypeId}
            value={issueType}
            onChange={(e) => setIssueType(e.target.value as FeedbackIssueType)}
            className="h-9 w-full rounded-md border border-border-default bg-bg-surface px-3 text-sm text-fg-primary focus:border-accent-primary focus:outline-none"
          >
            {FEEDBACK_ISSUE_TYPES.map((it) => (
              <option key={it} value={it}>
                {t(`feedback.issue_type.${it}`)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-1">
        <label
          htmlFor={notesId}
          className="text-xs font-semibold text-fg-primary"
        >
          {t("feedback.notes_label")}
        </label>
        <Textarea
          id={notesId}
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      {errorKey ? (
        <p role="alert" className="text-sm text-status-error">
          {t(errorKey)}
        </p>
      ) : null}
      {successId !== null ? (
        <p role="status" className="text-sm text-status-success">
          {t("feedback.success", { id: successId })}
        </p>
      ) : null}

      <Button type="submit" disabled={!canSubmit}>
        {submitting ? t("feedback.submitting") : t("feedback.submit_button")}
      </Button>
    </form>
  );
}
