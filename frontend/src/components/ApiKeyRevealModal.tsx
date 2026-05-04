import * as RadixDialog from "@radix-ui/react-dialog";
import { Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { useT } from "@/i18n/useT";
import type { ApiKeyOnce } from "@/stores/projects";

export function ApiKeyRevealModal({
  open,
  apiKey,
  onConfirmDismiss,
}: {
  open: boolean;
  apiKey: ApiKeyOnce;
  onConfirmDismiss: () => void;
}) {
  const t = useT();
  const [acked, setAcked] = useState(false);
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    void navigator.clipboard.writeText(apiKey.key);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  function handleDismiss() {
    if (!acked) return;
    setAcked(false);
    setCopied(false);
    onConfirmDismiss();
  }

  return (
    <RadixDialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next && acked) handleDismiss();
      }}
    >
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 bg-overlay/40" />
        <RadixDialog.Content className="fixed left-1/2 top-1/2 w-[min(40rem,92vw)] -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-md border border-border-default bg-bg-surface p-6 text-fg-primary shadow-lg">
          <RadixDialog.Title className="text-lg font-semibold">
            {t("publish.key_modal_title")}
          </RadixDialog.Title>
          <RadixDialog.Description className="text-sm text-status-warning">
            {t("publish.key_modal_warning")}
          </RadixDialog.Description>

          <section className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-fg-muted">
              {t("publish.key_modal_name_label")}: {apiKey.name}
            </p>
            <div className="flex items-center gap-2">
              <code
                className="flex-1 break-all rounded-sm border border-border-default bg-bg-muted px-2 py-1.5 font-mono text-sm text-fg-primary"
                aria-label={t("publish.key_modal_plaintext_label")}
              >
                {apiKey.key}
              </code>
              <Button
                variant="secondary"
                aria-label={t("publish.key_modal_copy_aria")}
                onClick={handleCopy}
              >
                <Copy size={14} className="mr-1" />
                {copied ? t("publish.key_modal_copied") : t("common.copy")}
              </Button>
            </div>
          </section>

          <label className="flex items-start gap-2 text-sm text-fg-primary">
            <input
              type="checkbox"
              checked={acked}
              onChange={(e) => setAcked(e.target.checked)}
              aria-label={t("publish.key_modal_ack_aria")}
            />
            <span>{t("publish.key_modal_ack_label")}</span>
          </label>

          <footer className="flex justify-end">
            <Button disabled={!acked} onClick={handleDismiss}>
              {t("publish.key_modal_dismiss")}
            </Button>
          </footer>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
