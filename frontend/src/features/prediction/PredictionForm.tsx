import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import type { PredictionFormState } from "../../types/prediction";
import { supportedPrefectures } from "../../utils/region";
import { buildingTypes, roomLayouts } from "./constants";

type Props = {
  value: PredictionFormState;
  onChange: (next: PredictionFormState) => void;
  stationOptions: string[];
  stationDistanceSource?: "map" | "manual";
  sheetState?: "collapsed" | "open";
  onSheetStateChange?: (state: "collapsed" | "open") => void;
  predictionYearRange?: {
    min: number;
    max: number;
  };
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
  stationDistanceSource = "manual",
  sheetState = "open",
  onSheetStateChange,
  predictionYearRange
}: Props) {
  const dragStartY = useRef<number | null>(null);
  const suppressNextClick = useRef(false);

  function update<K extends keyof PredictionFormState>(key: K, nextValue: PredictionFormState[K]) {
    onChange({ ...value, [key]: nextValue });
  }

  function handleDragStart(clientY: number) {
    dragStartY.current = clientY;
    suppressNextClick.current = false;
  }

  function handleDragEnd(clientY: number) {
    if (dragStartY.current === null) {
      return;
    }
    const deltaY = clientY - dragStartY.current;
    dragStartY.current = null;
    if (Math.abs(deltaY) < 24) {
      return;
    }
    suppressNextClick.current = true;
    onSheetStateChange?.(deltaY > 0 ? "collapsed" : "open");
    window.setTimeout(() => {
      suppressNextClick.current = false;
    }, 0);
  }

  function handleHandleClick() {
    if (suppressNextClick.current) {
      return;
    }
    onSheetStateChange?.(sheetState === "open" ? "collapsed" : "open");
  }

  return (
    <section className={`panel form-panel form-grid sheet-${sheetState}`}>
      <button
        type="button"
        className="sheet-handle"
        aria-label={sheetState === "open" ? "条件入力フォームを下げる" : "条件入力フォームを上げる"}
        onClick={handleHandleClick}
        onPointerDown={(event) => handleDragStart(event.clientY)}
        onPointerUp={(event) => handleDragEnd(event.clientY)}
      />
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

      <PredictionYearControl
        className="form-prediction-year"
        value={value.predictionYear}
        onChange={(nextValue) => update("predictionYear", nextValue)}
        predictionYearRange={predictionYearRange}
      />
    </section>
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
