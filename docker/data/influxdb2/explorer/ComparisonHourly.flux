//
// Compare Forecast
//

import "internal/debug"
import "timezone"
import "date"

//option location = timezone.location(name: "UTC")

fieldsCommon = ["UDC", "IDC", "UDC_2", "IDC_2"]
rES = 3600 // time resolution (s)

solar = from(bucket: "Fronius")
  |> range(start: date.sub(from: v.timeRangeStart, d: 1h), stop: date.add(to: v.timeRangeStop, d: 1s))
  |> filter(fn: (r) => (r["_measurement"] == "CommonInverterData" and contains(value: r._field, set: fieldsCommon)))
  |> aggregateWindow(every: duration(v: rES * 1000000000), fn: mean, createEmpty: false) // duration return ns
  |> pivot(rowKey: ["_time"], columnKey: ["_field", "_measurement"], valueColumn: "_value")
  |> map(fn: (r) => ({r with PowerSolarDC: (r.IDC_CommonInverterData * r.UDC_CommonInverterData
                                           + r.IDC_2_CommonInverterData * r.UDC_2_CommonInverterData) / 1000.
                             }))
  |> keep(columns:["_time",
                   "PowerSolarDC"])
  |> rename(columns: {
    _time: "Time",
    })


forecast = from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop: date.add(to: v.timeRangeStop, d: 1h))
  |> filter(fn: (r) => (r["_measurement"] == "Forecast" and r["_field"] == "forecast"))
  |> drop(columns: ["_measurement"])

//join(tables: {s: solar, p: forecast}, on: ["Time"])
union(tables: [solar, forecast])
  |> yield()