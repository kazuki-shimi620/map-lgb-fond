import { useState } from "react";

const STORAGE_KEY = "map-lgb-fond:onboarding-completed";

function hasCompletedGuide() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function useOnboardingGuide() {
  const [isOpen, setIsOpen] = useState(() => !hasCompletedGuide());

  function close() {
    setIsOpen(false);
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // Storage may be unavailable in private browsing. The guide can still be closed.
    }
  }

  return {
    isOpen,
    close,
    reopen: () => setIsOpen(true)
  };
}

export function OnboardingGuide({ onClose }: { onClose: () => void }) {
  return (
    <aside className="onboarding-guide" aria-label="はじめての使い方">
      <div>
        <strong>3ステップで価格を確認</strong>
        <ol>
          <li><span>1</span>地図で場所を選ぶ</li>
          <li><span>2</span>面積・築年数などを入力</li>
          <li><span>3</span>予測価格と理由を確認</li>
        </ol>
      </div>
      <button type="button" onClick={onClose}>わかりました</button>
    </aside>
  );
}
