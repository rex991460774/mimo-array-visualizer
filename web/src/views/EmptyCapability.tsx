import { Radar } from "lucide-react";
import { Button } from "../components/ui";
import { useT } from "../i18n";
import { useStore, type ViewId } from "../state/store";

export function EmptyCapability({
  title,
  body,
  actionView = "array",
}: {
  title: string;
  body?: string;
  actionView?: ViewId;
}) {
  const t = useT();
  const setView = useStore((state) => state.setView);
  return (
    <div className="empty-state">
      <div className="empty-state-inner">
        <Radar size={28} className="subtle" />
        <h3>{title}</h3>
        <p>{body ?? t("empty.body")}</p>
        <Button size="sm" onClick={() => setView(actionView)}>
          {actionView === "dbf1d" ? t("empty.view1d") : t("empty.editArray")}
        </Button>
      </div>
    </div>
  );
}
