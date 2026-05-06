import * as RadixAlertDialog from "@radix-ui/react-alert-dialog";

import { Button } from "@/components/ui/Button";
import { useT } from "@/i18n/useT";

// Dogfood follow-up #5: Revoke is destructive with no recall path. We use
// AlertDialog (not plain Dialog) so the surface advertises destructive
// intent via role="alertdialog" and Radix enforces the focus-trap +
// escape-to-cancel ergonomics expected for a destructive confirmation.
export function ConfirmRevokeKeyDialog({
  open,
  onOpenChange,
  keyName,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  keyName: string;
  onConfirm: () => void;
}) {
  const t = useT();
  return (
    <RadixAlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixAlertDialog.Portal>
        <RadixAlertDialog.Overlay className="fixed inset-0 bg-overlay/40" />
        <RadixAlertDialog.Content
          className="fixed left-1/2 top-1/2 w-[min(36rem,90vw)] -translate-x-1/2 -translate-y-1/2 rounded-md border border-border-default bg-bg-surface p-6 text-fg-primary shadow-lg"
        >
          <RadixAlertDialog.Title className="mb-3 text-lg font-semibold">
            {t("api_console.revoke_dialog_title")}
          </RadixAlertDialog.Title>
          <RadixAlertDialog.Description className="text-sm text-fg-primary">
            {t("api_console.revoke_dialog_body", { name: keyName })}
          </RadixAlertDialog.Description>
          <div className="mt-4 flex justify-end gap-2">
            <RadixAlertDialog.Cancel asChild>
              <Button variant="secondary">{t("common.cancel")}</Button>
            </RadixAlertDialog.Cancel>
            <RadixAlertDialog.Action asChild>
              <Button variant="danger" onClick={onConfirm}>
                {t("api_console.revoke_dialog_confirm")}
              </Button>
            </RadixAlertDialog.Action>
          </div>
        </RadixAlertDialog.Content>
      </RadixAlertDialog.Portal>
    </RadixAlertDialog.Root>
  );
}
