// Delete with an Undo toast: the item disappears at once; the DELETE is sent only when the toast's time is up.
import { useCallback, useState } from "react";
import { useLibrary } from "../../app/contexts";
import { useToast } from "../../design/components/toastContext";
import { useI18n } from "../../i18n";

export const UNDO_MS = 6000;

/** hidden: ids waiting to be deleted (hide them); remove(id, del): hide, offer Undo, then run del. */
export function useUndoDelete(): {
  hidden: ReadonlySet<string>;
  remove: (id: string, del: () => Promise<unknown>) => void;
} {
  const { t } = useI18n();
  const toast = useToast();
  const { bump } = useLibrary();
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());

  const show = useCallback((id: string, visible: boolean) => {
    setHidden((current) => {
      const next = new Set(current);
      if (visible) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const remove = useCallback(
    (id: string, del: () => Promise<unknown>) => {
      show(id, false);
      let undone = false;
      toast({
        title: t("deleted_toast"),
        tone: "info",
        duration: UNDO_MS,
        action: {
          label: t("undo"),
          onSelect: () => {
            undone = true;
            show(id, true);
          },
        },
      });
      setTimeout(() => {
        if (undone) return;
        del().then(bump, () => {
          show(id, true);
          toast({ title: t("library_error"), tone: "danger" });
        });
      }, UNDO_MS);
    },
    [bump, show, t, toast],
  );

  return { hidden, remove };
}
