import { FolderOpen, Save, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { ProjectSummary } from "../api/types";
import { Button, Callout, Dialog, Spinner } from "../components/ui";
import { useT } from "../i18n";
import { openProject, saveProject } from "../state/actions";
import { useIsDirty, useStore } from "../state/store";

export function ProjectsDialog({ onClose }: { onClose: () => void }) {
  const t = useT();
  const language = useStore((state) => state.language);
  const projectId = useStore((state) => state.projectId);
  const dirty = useIsDirty();
  const [items, setItems] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api.listProjects().then(
      (result) => {
        setItems(result);
        setError(null);
      },
      (reason) => setError(errorMessage(reason)),
    );
  }, []);
  useEffect(refresh, [refresh]);

  const format = (iso: string) => {
    try {
      return new Date(iso).toLocaleString(language === "zh" ? "zh-CN" : language === "ja" ? "ja-JP" : "en-US");
    } catch {
      return iso;
    }
  };

  return (
    <Dialog
      title={t("projectsDialog.title")}
      onClose={onClose}
      footer={
        <>
          <span className="subtle" style={{ fontSize: 12 }}>
            {t("projectsDialog.hint")}
          </span>
          <span className="spacer" />
          <Button
            variant="primary"
            icon={<Save size={15} />}
            onClick={async () => {
              await saveProject();
              refresh();
            }}
          >
            {t("projectsDialog.saveCurrent")}
          </Button>
        </>
      }
    >
      {error && <Callout tone="danger">{error}</Callout>}
      {dirty && projectId && (
        <div style={{ marginBottom: 12 }}>
          <Callout tone="warning">{t("projectsDialog.discard")}</Callout>
        </div>
      )}
      {!items && !error && <Spinner />}
      {items && items.length === 0 && <p className="subtle">{t("projectsDialog.empty")}</p>}
      <div className="project-list">
        {items?.map((item) => (
          <div key={item.id} className="project-row">
            <div className="meta">
              <div className="name">
                {item.name || t("project.untitled")}{" "}
                {item.id === projectId && <span className="badge ok">{t("projectsDialog.current")}</span>}
              </div>
              <div className="subtle" style={{ fontSize: 12 }}>
                {item.tx_count}T{item.rx_count}R · {item.frequency_ghz ?? "—"} GHz ·{" "}
                {t("projectsDialog.updated", { time: format(item.updated_at) })}
              </div>
            </div>
            <Button
              size="sm"
              icon={<FolderOpen size={13} />}
              onClick={async () => {
                await openProject(item.id);
                onClose();
              }}
            >
              {t("projectsDialog.open")}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="danger"
              icon={<Trash2 size={13} />}
              aria-label={t("projectsDialog.delete")}
              title={t("projectsDialog.delete")}
              onClick={async () => {
                if (!window.confirm(t("projectsDialog.confirmDelete", { name: item.name }))) return;
                try {
                  await api.deleteProject(item.id);
                  if (item.id === projectId) useStore.setState({ projectId: null, savedSnapshot: null });
                  refresh();
                } catch (reason) {
                  setError(errorMessage(reason));
                }
              }}
            />
          </div>
        ))}
      </div>
    </Dialog>
  );
}
