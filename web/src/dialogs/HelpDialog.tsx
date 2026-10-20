import { useState } from "react";
import { Dialog } from "../components/ui";
import { useT } from "../i18n";
import { HELP, SHORTCUTS } from "../i18n/help";
import { useStore } from "../state/store";

export function HelpDialog({ onClose }: { onClose: () => void }) {
  const t = useT();
  const language = useStore((state) => state.language);
  const sections = HELP[language];
  const [active, setActive] = useState(sections[0].id);
  const section = sections.find((item) => item.id === active);

  return (
    <Dialog title={t("help.title")} onClose={onClose} size="medium">
      <div className="help-layout">
        <nav className="help-nav">
          {sections.map((item) => (
            <button key={item.id} type="button" aria-current={item.id === active} onClick={() => setActive(item.id)}>
              {item.title}
            </button>
          ))}
          <button type="button" aria-current={active === "shortcuts"} onClick={() => setActive("shortcuts")}>
            {t("help.shortcuts")}
          </button>
        </nav>
        <div className="help-content">
          {section && (
            <>
              <h3>{section.title}</h3>
              {section.paragraphs?.map((text) => <p key={text}>{text}</p>)}
              {section.steps && (
                <ol>
                  {section.steps.map((text) => (
                    <li key={text}>{text}</li>
                  ))}
                </ol>
              )}
              {section.bullets && (
                <ul>
                  {section.bullets.map((text) => (
                    <li key={text}>{text}</li>
                  ))}
                </ul>
              )}
            </>
          )}
          {active === "shortcuts" && (
            <>
              <h3>{t("help.shortcuts")}</h3>
              <table className="table">
                <tbody>
                  {SHORTCUTS.map((item) => (
                    <tr key={item[language]}>
                      <td style={{ width: 170 }}>
                        {item.keys.map((key) => (
                          <span key={key} className="kbd" style={{ marginRight: 4 }}>
                            {key}
                          </span>
                        ))}
                      </td>
                      <td>{item[language]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </Dialog>
  );
}
