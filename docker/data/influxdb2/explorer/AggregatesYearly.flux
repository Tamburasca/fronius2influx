// import "experimental"
from(bucket: "aggregates")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) =>
    r._measurement == "daily")
  |> aggregateWindow(every: 1y, fn: sum, createEmpty:false)
  |> timeShift(duration: -3h)
  |> drop(columns: ["_measurement"])
// |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
// |> map(fn: (r) => ({r with "percentage1": r.UsageDirect / r.PowerSolarDC}))
// |> experimental.unpivot()