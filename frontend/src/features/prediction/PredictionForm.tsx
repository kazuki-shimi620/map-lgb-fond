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
import { supportedPrefectures } from "../../utils/region";
import { buildingTypes, roomLayouts } from "./constants";

type Props = {
  value: PredictionFormState;
  onChange: (next: PredictionFormState) => void;
  stationOptions: string[];
  futureScenario: FutureScenario;
  onFutureScenarioChange: (next: FutureScenario) => void;
  stationDistanceSource?: "map" | "manual";
  sheetState?: "collapsed" | "half" | "open";
  predictionYearRange?: {
    min: number;
    max: number;
  };
  formRef?: Ref<HTMLElement>;
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
  stationOptions,
  futureScenario,
  onFutureScenarioChange,
  stationDistanceSource = "manual",
  sheetState = "open",
  predictionYearRange,
  formRef
}: Props) {
  function update<K extends keyof PredictionFormState>(key: K, nextValue: PredictionFormState[K]) {
    onChange({ ...value, [key]: nextValue });
  }

  return (
    <>
      <section
        ref={formRef}
        className={`panel form-panel form-grid sheet-${sheetState}`}
        data-testid="prediction-form"
      >
        <SelectField
          label="都道府県"
          value={value.prefecture}
          options={supportedPrefectures}
          onChange={(nextValue) => update("prefecture", nextValue)}
        />

        <label>
          市区町村
          <input value={value.municipality} onChange={(event) => update("municipality", event.target.value)} />
        </label>

        <label>
          最寄駅
          <input list="station-suggestions" value={value.station} onChange={(event) => update("station", event.target.value)} />
          <datalist id="station-suggestions">
            {stationOptions.map((station) => (
              <option key={station} value={station} />
            ))}
          </datalist>
        </label>

        <label>
          面積
          <input
            type="number"
            min="1"
            value={value.area}
            onChange={(event) => update("area", Number(event.target.value))}
          />
        </label>

        <label>
          築年数
          <input
            type="number"
            min="0"
            value={value.age}
            onChange={(event) => update("age", Number(event.target.value))}
          />
        </label>

        <label>
          駅徒歩
          <input
            type="number"
            min="0"
            step="any"
            value={value.stationDistance}
            onChange={(event) => update("stationDistance", Number(event.target.value))}
          />
          <span className="field-note">
            {stationDistanceSource === "map" ? "地図から自動算出" : "手入力"}
          </span>
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
    </>
  );
}

export function PredictionSheetHandle({
  sheetState,
  onSheetStateChange
}: PredictionSheetHandleProps) {
  const dragState = useRef<{ pointerId: number; startY: number; didDrag: boolean } | null>(null);

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
      aria-label={sheetState === "open" ? "条件入力フォームを下げる" : "条件入力フォームを上げる"}
      onClick={(event) => {
        event.preventDefault();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
        }
      }}
      onPointerDown={handleDragStart}
      onPointerMove={handleDragMove}
      onPointerUp={handleDragEnd}
      onPointerCancel={handleDragCancel}
    >
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

  function commitValue(nextValue: string) {
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
        type="button"
        className="custom-select-trigger"
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
