import "timezone"

option location = timezone.location(name: "Europe/Berlin")

from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "Forecast" and r["_field"] == "ssrd")
  |> aggregateWindow(every: 1d, offset: -1m, fn: sum)
