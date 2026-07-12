import { useId, useMemo, useState, type ReactNode } from "react";

export type SupportingInfoTab = {
  id: string;
  label: string;
  description: string;
  content: ReactNode;
};

type Props = {
  tabs: SupportingInfoTab[];
};

export function SupportingInfoTabs({ tabs }: Props) {
  const [activeTabId, setActiveTabId] = useState(tabs[0]?.id ?? "");
  const groupId = useId();
  const activeTab = useMemo(
    () => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0],
    [activeTabId, tabs]
  );

  if (!activeTab) {
    return null;
  }

  return (
    <section className="panel supporting-info-section" aria-label="参考情報" data-testid="supporting-info-tabs">
      <div className="supporting-info-header">
        <div>
          <h2>参考情報</h2>
          <p className="muted">商業施設、駅規模、災害リスク、モデル詳細を必要に応じて確認できます。</p>
        </div>
        <div className="supporting-info-tabs" role="tablist" aria-label="参考情報の切り替え">
          {tabs.map((tab) => {
            const tabId = `${groupId}-${tab.id}-tab`;
            const panelId = `${groupId}-${tab.id}-panel`;
            const isSelected = tab.id === activeTab.id;
            return (
              <button
                key={tab.id}
                type="button"
                id={tabId}
                role="tab"
                aria-selected={isSelected}
                aria-controls={panelId}
                className={isSelected ? "is-selected" : ""}
                onClick={() => setActiveTabId(tab.id)}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      <div
        className="supporting-info-content"
        id={`${groupId}-${activeTab.id}-panel`}
        role="tabpanel"
        aria-labelledby={`${groupId}-${activeTab.id}-tab`}
      >
        <p className="supporting-info-description">{activeTab.description}</p>
        {activeTab.content}
      </div>
    </section>
  );
}
