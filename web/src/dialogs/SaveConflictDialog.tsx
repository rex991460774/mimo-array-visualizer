import { CopyPlus, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Button, Callout, Dialog } from "../components/ui";
import { useT } from "../i18n";
import { saveProject } from "../state/actions";
import { useStore } from "../state/store";

/** Shown when a save is refused because someone else saved the library project first. */
export function SaveConflictDialog({ onClose }: { onClose: () => void }) {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const projectId = useStore((state) => state.projectId);
  const language = useStore((state) => state.language);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    api.getProject(projectId).then(
      (record) => {
        if (cancelled) return;
        const locale = language === "zh" ? "zh-CN" : language === "ja" ? "ja-JP" : "en-US";
        setSavedAt(new Date(record.updated_at).toLocaleString(locale));
      },
      () => undefined,
    );
    return () => {
      cancelled = true;
    };
  }, [projectId, language]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    onClose();
    await action();
    setBusy(false);
  };

  return (
    <Dialog
      title={t("conflict.title")}
      onClose={onClose}
      footer={
        <>
          <span className="spacer" />
          <Button onClick={onClose} disabled={busy}>
            {t("conflict.cancel")}
          </Button>
          <Button variant="danger" icon={<Save size={15} />} disabled={busy} onClick={() => run(() => saveProject(false, true))}>
            {t("conflict.overwrite")}
          </Button>
          <Button
            variant="primary"
            icon={<CopyPlus size={15} />}
            disabled={busy}
            onClick={() =>
              run(async () => {
                useStore.getState().updateProject({ name: `${project.name}${t("conflict.copySuffix")}`.slice(0, 120) });
                await saveProject(true);
              })
            }
          >
            {t("conflict.saveAsNew")}
          </Button>
        </>
      }
    >
      <div className="section">
        <Callout tone="warning">{t("conflict.body", { name: project.name, time: savedAt ?? "—" })}</Callout>
        <p className="subtle" style={{ margin: 0 }}>
          {t("conflict.keep")}
        </p>
      </div>
    </Dialog>
  );
}
