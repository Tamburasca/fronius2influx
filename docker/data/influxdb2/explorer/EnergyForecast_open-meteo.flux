import "timezone"

from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "Forecast" and r["_field"] == "forecast")
  |> aggregateWindow(every: 1d, offset: -1m, fn: sum)