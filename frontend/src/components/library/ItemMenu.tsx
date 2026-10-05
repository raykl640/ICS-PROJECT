import { FolderInput, MoreVertical, Pencil, Pin, PinOff, Trash2 } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { listMatters, type Matter } from "../../api/library";
import { Button, IconButton } from "../../design/components/Button";
import { Dialog, DialogContent } from "../../design/components/Dialog";
import { Field, Select } from "../../design/components/Field";
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from "../../design/components/Menu";
import { useI18n } from "../../i18n";
import limits from "../../limits.json";

interface ItemMenuProps {
  /** The item's name, for the menu button's accessible name. */
  title: string;
  pinned?: boolean;
  onPin?: (pinned: boolean) => void;
  onRename?: (name: string) => Promise<void>;
  matterId?: string | null;
  onMove?: (matterId: string | null) => Promise<void>;
  onDelete: () => void;
}

type Open = "none" | "rename" | "move";

/** "⋮" menu of a library item: pin, rename, move to a matter, delete (each only if the item supports it). */
export function ItemMenu({ title, pinned, onPin, onRename, matterId, onMove, onDelete }: ItemMenuProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState<Open>("none");
  return (
    <>
      <Menu>
        <MenuTrigger asChild>
          <IconButton label={t("item_actions", { title })} icon={<MoreVertical size={20} />} />
        </MenuTrigger>
        <MenuContent>
          {onPin && (
            <MenuItem icon={pinned ? <PinOff size={18} /> : <Pin size={18} />} onSelect={() => onPin(!pinned)}>
              {t(pinned ? "action_unpin" : "action_pin")}
            </MenuItem>
          )}
          {onRename && (
            <MenuItem icon={<Pencil size={18} />} onSelect={() => setOpen("rename")}>
              {t("action_rename")}
            </MenuItem>
          )}
          {onMove && (
            <MenuItem icon={<FolderInput size={18} />} onSelect={() => setOpen("move")}>
              {t("action_move")}
            </MenuItem>
          )}
          <MenuSeparator />
          <MenuItem icon={<Trash2 size={18} />} tone="danger" onSelect={onDelete}>
            {t("action_delete")}
          </MenuItem>
        </MenuContent>
      </Menu>
      {onRename && open === "rename" && (
        <RenameDialog initial={title} onClose={() => setOpen("none")} onSave={onRename} />
      )}
      {onMove && open === "move" && (
        <MoveDialog current={matterId ?? null} onClose={() => setOpen("none")} onMove={onMove} />
      )}
    </>
  );
}

/** Mounted only while open, so it starts from the current name each time. */
function RenameDialog({
  initial,
  onClose,
  onSave,
}: {
  initial: string;
  onClose: () => void;
  onSave: (name: string) => Promise<void>;
}) {
  const { t } = useI18n();
  const [name, setName] = useState(initial);
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      await onSave(name.trim());
      onClose();
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent title={t("action_rename")} closeLabel={t("dismiss")}>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field
            label={t("rename_label")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={limits.title_max_chars}
          />
          <div className="flex justify-end gap-2">
            <Button onClick={onClose}>{t("cancel")}</Button>
            <Button type="submit" variant="primary" disabled={busy || !name.trim()}>
              {t("save")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Mounted only while open; loads the user's matters each time. */
function MoveDialog({
  current,
  onClose,
  onMove,
}: {
  current: string | null;
  onClose: () => void;
  onMove: (matterId: string | null) => Promise<void>;
}) {
  const { t } = useI18n();
  const [matters, setMatters] = useState<Matter[] | null>(null);
  const [choice, setChoice] = useState(current ?? "");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    listMatters().then(
      (page) => live && setMatters(page.items),
      () => live && setMatters([]),
    );
    return () => {
      live = false;
    };
  }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await onMove(choice || null);
      onClose();
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent title={t("action_move")} closeLabel={t("dismiss")} description={t("matters_hint")}>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Select
            label={t("move_label")}
            value={choice}
            onChange={(e) => setChoice(e.target.value)}
            options={[
              { value: "", label: t("move_none") },
              ...(matters ?? []).map((m) => ({ value: m.id, label: m.name })),
            ]}
          />
          {matters?.length === 0 && <p className="text-sm text-ink-muted">{t("matters_empty")}</p>}
          <div className="flex justify-end gap-2">
            <Button onClick={onClose}>{t("cancel")}</Button>
            <Button type="submit" variant="primary" disabled={busy}>
              {t("save")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
