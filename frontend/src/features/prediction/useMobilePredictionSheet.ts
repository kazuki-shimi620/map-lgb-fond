import { useEffect, useRef, useState } from "react";

export type PredictionSheetState = "collapsed" | "half" | "open";

export function useMobilePredictionSheet() {
  const [formSheetState, setFormSheetState] = useState<PredictionSheetState>("collapsed");
  const formPanelRef = useRef<HTMLElement | null>(null);
  const sheetStackRef = useRef<HTMLDivElement | null>(null);
  const scrollAnimationRef = useRef<number | null>(null);
  const mapSelectionScrollTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      clearPendingMapSelectionScroll();
    };
  }, []);

  function clearPendingMapSelectionScroll() {
    if (mapSelectionScrollTimerRef.current !== null) {
      window.clearTimeout(mapSelectionScrollTimerRef.current);
      mapSelectionScrollTimerRef.current = null;
    }
  }

  function scrollToFormAfterMapSelection(delayMs: number) {
    clearPendingMapSelectionScroll();

    mapSelectionScrollTimerRef.current = window.setTimeout(() => {
      mapSelectionScrollTimerRef.current = null;
      setFormSheetState("half");
      window.requestAnimationFrame(() => {
        if (window.matchMedia("(max-width: 760px)").matches) {
          sheetStackRef.current?.scrollTo({ top: 0, behavior: "smooth" });
          return;
        }
        if (formPanelRef.current) {
          animateScrollToElement(formPanelRef.current, scrollAnimationRef);
        }
      });
    }, delayMs);
  }

  return {
    clearPendingMapSelectionScroll,
    formPanelRef,
    formSheetState,
    scrollToFormAfterMapSelection,
    setFormSheetState,
    sheetStackRef
  };
}

function animateScrollToElement(
  element: HTMLElement,
  animationRef: { current: number | null }
) {
  if (animationRef.current !== null) {
    window.cancelAnimationFrame(animationRef.current);
  }

  const startY = window.scrollY;
  const targetY = startY + element.getBoundingClientRect().top;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    window.scrollTo(0, targetY);
    animationRef.current = null;
    return;
  }

  const distance = targetY - startY;
  const duration = 1000;
  const startTime = performance.now();

  function step(now: number) {
    const progress = Math.min(1, (now - startTime) / duration);
    const eased =
      progress < 0.5
        ? 4 * progress * progress * progress
        : 1 - Math.pow(-2 * progress + 2, 3) / 2;
    window.scrollTo(0, startY + distance * eased);
    if (progress < 1) {
      animationRef.current = window.requestAnimationFrame(step);
    } else {
      animationRef.current = null;
    }
  }

  animationRef.current = window.requestAnimationFrame(step);
}
