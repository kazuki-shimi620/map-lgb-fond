import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type Ref
} from "react";
import type { PredictionFormState } from "../../types/prediction";
import { buildingTypes, roomLayouts } from "./constants";

type Props = {
  value: PredictionFormState;
  onChange: (next: PredictionFormState) => void;
  futureScenario: FutureScenario;
  onFutureScenarioChange: (next: FutureScenario) => void;
  sheetState?: "collapsed" | "half" | "open";
  predictionYearRange?: {
    min: number;
    max: number;
  };
  formRef?: Ref<HTMLElement>;
};

type PropertyConditionFormProps = {
  value: PredictionFormState;
  onChange: (next: PredictionFormState) => void;
  sheetState?: "collapsed" | "half" | "open";
  formRef?: Ref<HTMLElement>;
};

type ForecastControlsProps = {
  value: PredictionFormState;
  onChange: (next: PredictionFormState) => void;
  futureScenario: FutureScenario;
  onFutureScenarioChange: (next: FutureScenario) => void;
  predictionYearRange?: {
    min: number;
    max: number;
  };
};

type PredictionSheetHandleProps = {
  sheetState: "collapsed" | "half" | "open";
  onSheetStateChange: (state: "collapsed" | "half" | "open") => void;
};

type PredictionYearControlProps = {
  value: number;
  onChange: (next: number) => void;
  predictionYearRange?: {
    min: number;
    max: number;
  };
  className?: string;
};

export type FutureScenario = "bear" | "flat" | "base" | "bull";

type FutureScenarioControlProps = {
  value: FutureScenario;
  onChange: (next: FutureScenario) => void;
};

type SelectFieldProps = {
  label: string;
  value: string;
  options: string[];
  onChange: (nextValue: string) => void;
};

export function PredictionForm({
  value,
  onChange,
  futureScenario,
  onFutureScenarioChange,
  sheetState = "open",
  predictionYearRange,
  formRef
}: Props) {
  return (
    <>
      <PropertyConditionForm
        formRef={formRef}
        value={value}
        onChange={onChange}
        sheetState={sheetState}
      />
      <ForecastControls
        value={value}
        onChange={onChange}
        futureScenario={futureScenario}
        onFutureScenarioChange={onFutureScenarioChange}
        predictionYearRange={predictionYearRange}
      />
    </>
  );
}

export function PropertyConditionForm({
  value,
  onChange,
  sheetState = "open",
  formRef
}: PropertyConditionFormProps) {
  function update<K extends keyof PredictionFormState>(key: K, nextValue: PredictionFormState[K]) {
    onChange({ ...value, [key]: nextValue });
  }

  return (
    <section
      ref={formRef}
      className={`panel form-panel form-grid sheet-${sheetState}`}
      data-testid="prediction-form"
    >
      <label>
        面積
        <input
          id="property-area"
          name="area"
          type="number"
          min="1"
          value={value.area}
          onChange={(event) => update("area", Number(event.target.value))}
        />
      </label>

      <label>
        築年数
        <input
          id="property-age"
          name="age"
          type="number"
          min="0"
          value={value.age}
          onChange={(event) => update("age", Number(event.target.value))}
        />
      </label>

      <SelectField
        label="間取り"
        value={value.roomLayout}
        options={roomLayouts}
        onChange={(nextValue) => update("roomLayout", nextValue)}
      />

      <SelectField
        label="建物構造"
        value={value.buildingType}
        options={buildingTypes}
        onChange={(nextValue) => update("buildingType", nextValue)}
      />
    </section>
  );
}

export function ForecastControls({
  value,
  onChange,
  futureScenario,
  onFutureScenarioChange,
  predictionYearRange
}: ForecastControlsProps) {
  function update<K extends keyof PredictionFormState>(key: K, nextValue: PredictionFormState[K]) {
    onChange({ ...value, [key]: nextValue });
  }

  return (
    <section
      className="panel forecast-panel"
      aria-label="予測年と将来シナリオ"
      data-testid="prediction-forecast-controls"
    >
      <PredictionYearControl
        className="form-prediction-year"
        value={value.predictionYear}
        onChange={(nextValue) => update("predictionYear", nextValue)}
        predictionYearRange={predictionYearRange}
      />

      <FutureScenarioControl
        value={futureScenario}
        onChange={onFutureScenarioChange}
      />
    </section>
  );
}

export function PredictionSheetHandle({
  sheetState,
  onSheetStateChange
}: PredictionSheetHandleProps) {
  const dragState = useRef<{ pointerId: number; startY: number; didDrag: boolean } | null>(null);
  const suppressNextClick = useRef(false);

  function handleDragStart(event: ReactPointerEvent<HTMLButtonElement>) {
    dragState.current = {
      pointerId: event.pointerId,
      startY: event.clientY,
      didDrag: false
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handleDragMove(event: ReactPointerEvent<HTMLButtonElement>) {
    const currentDrag = dragState.current;
    if (!currentDrag || currentDrag.pointerId !== event.pointerId || currentDrag.didDrag) {
      return;
    }

    const deltaY = event.clientY - currentDrag.startY;
    if (Math.abs(deltaY) < 36) {
      return;
    }

    currentDrag.didDrag = true;
    onSheetStateChange(deltaY > 0 ? "collapsed" : "open");
  }

  function handleDragEnd(event: ReactPointerEvent<HTMLButtonElement>) {
    suppressNextClick.current = dragState.current?.didDrag ?? false;
    dragState.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function handleDragCancel(event: ReactPointerEvent<HTMLButtonElement>) {
    dragState.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  return (
    <button
      type="button"
      className="sheet-header"
      data-testid="sheet-handle"
      aria-label={sheetState === "collapsed" ? "条件メニューを開く" : "条件メニューを閉じる"}
      onClick={(event) => {
        event.preventDefault();
        if (suppressNextClick.current) {
          suppressNextClick.current = false;
          return;
        }
        onSheetStateChange(sheetState === "collapsed" ? "open" : "collapsed");
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSheetStateChange(sheetState === "collapsed" ? "open" : "collapsed");
        }
      }}
      onPointerDown={handleDragStart}
      onPointerMove={handleDragMove}
      onPointerUp={handleDragEnd}
      onPointerCancel={handleDragCancel}
    >
      <span className="sidebar-title">条件・予測</span>
      <span className="sheet-handle" aria-hidden="true" />
    </button>
  );
}

export function PredictionYearControl({
  value,
  onChange,
  predictionYearRange,
  className = ""
}: PredictionYearControlProps) {
  return (
    <label className={`prediction-year-field ${className}`}>
      <span className="field-heading">
        予測年
        <strong>{value}年</strong>
      </span>
      {predictionYearRange ? (
        <>
          <input
            id="prediction-year-range"
            name="predictionYearRange"
            type="range"
            min={predictionYearRange.min}
            max={predictionYearRange.max}
            step="1"
            value={value}
            onChange={(event) => onChange(Number(event.target.value))}
          />
          <span className="year-scale">
            <span>{predictionYearRange.min}</span>
            <span>{predictionYearRange.max}</span>
          </span>
        </>
      ) : null}
      <input
        id="prediction-year"
        name="predictionYear"
        type="number"
        min={predictionYearRange?.min ?? 1990}
        max={predictionYearRange?.max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

function FutureScenarioControl({ value, onChange }: FutureScenarioControlProps) {
  const tooltipId = useId();
  const scenarios: Array<{ value: FutureScenario; label: string }> = [
    { value: "bear", label: "弱気" },
    { value: "flat", label: "横ばい" },
    { value: "base", label: "標準" },
    { value: "bull", label: "強気" }
  ];

  return (
    <div className="future-scenario-field">
      <span className="field-heading">
        <span className="scenario-label">
          将来シナリオ
          <span className="scenario-info">
            <button type="button" className="info-icon-button" aria-label="将来シナリオの説明" aria-describedby={tooltipId}>
              i
            </button>
            <span className="scenario-tooltip" id={tooltipId} role="tooltip">
              横ばいは将来補正を0%に固定します。標準は駅または地域の過去トレンドを使い、弱気・強気は標準を基準に上下へ補正します。
            </span>
          </span>
        </span>
        <strong>{scenarios.find((scenario) => scenario.value === value)?.label}</strong>
      </span>
      <div className="segmented-control" role="radiogroup" aria-label="将来シナリオ">
        {scenarios.map((scenario) => (
          <button
            key={scenario.value}
            type="button"
            role="radio"
            aria-checked={scenario.value === value}
            className={scenario.value === value ? "is-selected" : ""}
            onClick={() => onChange(scenario.value)}
          >
            {scenario.label}
          </button>
        ))}
      </div>
      <span className="field-note">過去トレンドから作る参考レンジ</span>
    </div>
  );
}

function SelectField({ label, value, options, onChange }: SelectFieldProps) {
  const [isOpen, setIsOpen] = useState(false);
  const fieldRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const restoreFocusRef = useRef(false);
  const listboxId = useId();

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      if (!fieldRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [isOpen]);

  useEffect(() => {
    if (!restoreFocusRef.current) return;
    restoreFocusRef.current = false;
    triggerRef.current?.focus();
  }, [value]);

  function commitValue(nextValue: string) {
    restoreFocusRef.current = true;
    onChange(nextValue);
    setIsOpen(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const currentIndex = Math.max(0, options.indexOf(value));
    if (event.key === "ArrowDown") {
      event.preventDefault();
      commitValue(options[Math.min(options.length - 1, currentIndex + 1)]);
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      commitValue(options[Math.max(0, currentIndex - 1)]);
    }
    if (event.key === "Escape") {
      setIsOpen(false);
    }
  }

  return (
    <div className="form-field custom-select-field" ref={fieldRef}>
      <span>{label}</span>
      <button
        ref={triggerRef}
        type="button"
        className="custom-select-trigger"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        onClick={() => setIsOpen((current) => !current)}
        onKeyDown={handleKeyDown}
      >
        <span>{value}</span>
        <span className="custom-select-chevron" aria-hidden="true" />
      </button>
      <div
        className={`custom-select-menu ${isOpen ? "is-open" : ""}`}
        id={listboxId}
        role="listbox"
        tabIndex={-1}
        aria-label={`${label}の選択肢`}
        aria-hidden={!isOpen}
      >
        {options.map((option) => (
          <button
            key={option}
            type="button"
            className={option === value ? "is-selected" : ""}
            role="option"
            aria-selected={option === value}
            tabIndex={isOpen ? 0 : -1}
            onClick={() => commitValue(option)}
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}
