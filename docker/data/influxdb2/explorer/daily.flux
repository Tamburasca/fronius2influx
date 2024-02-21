from(bucket: "aggregates")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) =>
    r._measurement == "daily")
  |> drop(columns: ["_measurement"])