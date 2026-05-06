import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { useT } from "@/i18n/useT";

// Dogfood follow-up #5: Revoke is destructive with no recall path —
// gating it behind a confirmation matches the rest of the Danger zone
// semantics. Reusing the existing Dialog wrapper keeps the dependency
// surface unchanged; if a future incident shows we need
// role="alertdialog" / focus-trap escape semantics, install
// @radix-ui/react-alert-dialog then.
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
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("api_console.revoke_dialog_title")}
    >
      <div className="space-y-3 text-sm">
        <p className="text-fg-primary">
          {t("api_console.revoke_dialog_body", { name: keyName })}
        </p>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button variant="danger" onClick={onConfirm}>
            {t("api_console.revoke_dialog_confirm")}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
