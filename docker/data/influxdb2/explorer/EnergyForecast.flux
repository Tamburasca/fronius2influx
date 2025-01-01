import "timezone"

option location = timezone.location(name: "Europe/Berlin")

RES = 86400 // time resolution
from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "Forecast" and r["_field"] == "ssrd")
  |> aggregateWindow(every: duration(v: RES * 1000000000), offset: -1h, fn: sum)
