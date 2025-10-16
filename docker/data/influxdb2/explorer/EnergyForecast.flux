import "timezone"
import "strings"

from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "Forecast" and contains(value: r["_field"], set: ["forecast", "ssrd"]))
  |> aggregateWindow(every: 1d, offset: -1m, fn: sum)
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field, t: "ssrd", u: "ECMWF")}))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field, t: "forecast", u: "open-meteo")}))