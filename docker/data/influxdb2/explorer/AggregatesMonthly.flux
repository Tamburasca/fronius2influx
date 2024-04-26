from(bucket: "aggregates")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) =>
    r._measurement == "daily")
  |> aggregateWindow(every: 1mo, fn: sum, createEmpty:false)
  |> timeShift(duration: -3h)
  |> drop(columns: ["_measurement"])