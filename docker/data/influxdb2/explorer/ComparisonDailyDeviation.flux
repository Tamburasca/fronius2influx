import "timezone"

option location = timezone.location(name: "Europe/Berlin")

solar = from(bucket: "aggregates")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "daily" and r._field == "PowerSolarDC")
  |> keep(columns: ["_time", "_value"])

pred = from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "Forecast" and r._field == "forecast")
  |> aggregateWindow(every: 1d, offset: -1m, fn: sum)
  |> keep(columns: ["_time", "_value"])

join(tables: {s: solar, p: pred}, on: ["_time"])
  |> map(fn: (r) => ({r with deviation: (r._value_p - r._value_s) / r._value_s * 100.}))
  |> keep(columns: ["_time", "deviation"])