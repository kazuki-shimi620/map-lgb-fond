import type { FormEvent } from "react";
import type { PredictionFormState } from "../../types/prediction";
import { supportedPrefectures } from "../../utils/region";
import { buildingTypes, roomLayouts } from "./constants";

type Props = {
  value: PredictionFormState;
  onChange: (next: PredictionFormState) => void;
  onSubmit: () => void;
  stationOptions: string[];
  disabled?: boolean;
};

export function PredictionForm({ value, onChange, onSubmit, stationOptions, disabled = false }: Props) {
  function update<K extends keyof PredictionFormState>(key: K, nextValue: PredictionFormState[K]) {
    onChange({ ...value, [key]: nextValue });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form className="panel form-grid" onSubmit={handleSubmit}>
      <label>
        都道府県
        <select value={value.prefecture} onChange={(event) => update("prefecture", event.target.value)}>
          {supportedPrefectures.map((prefecture) => (
            <option key={prefecture} value={prefecture}>
              {prefecture}
            </option>
          ))}
        </select>
      </label>

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
          value={value.stationDistance}
          onChange={(event) => update("stationDistance", Number(event.target.value))}
        />
      </label>

      <label>
        間取り
        <select value={value.roomLayout} onChange={(event) => update("roomLayout", event.target.value)}>
          {roomLayouts.map((layout) => (
            <option key={layout} value={layout}>
              {layout}
            </option>
          ))}
        </select>
      </label>

      <label>
        建物構造
        <select value={value.buildingType} onChange={(event) => update("buildingType", event.target.value)}>
          {buildingTypes.map((buildingType) => (
            <option key={buildingType} value={buildingType}>
              {buildingType}
            </option>
          ))}
        </select>
      </label>

      <label>
        予測年
        <input
          type="number"
          min="1990"
          value={value.predictionYear}
          onChange={(event) => update("predictionYear", Number(event.target.value))}
        />
      </label>

      <button className="primary-action" type="submit" disabled={disabled}>
        予測
      </button>
    </form>
  );
}
