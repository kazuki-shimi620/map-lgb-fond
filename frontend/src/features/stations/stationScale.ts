import type { StationRecord } from "../../types/assets";

export type StationScaleRequestFields = {
  stationPassengerLog: number;
  stationLineCount: number;
  stationOperatorCount: number;
  stationRank: string;
};

export function buildStationScaleRequestFields(
  stations: StationRecord[],
  stationName: string
): StationScaleRequestFields {
  const station = stations.find((candidate) => candidate.station_name === stationName);
  return {
    stationPassengerLog: station?.station_passenger_log ?? 0,
    stationLineCount: station?.station_line_count ?? 0,
    stationOperatorCount: station?.station_operator_count ?? 0,
    stationRank: station?.station_rank ?? "unknown"
  };
}
