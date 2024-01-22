//
// Collected Solar Power
//
fields = ["UDC", "IDC", "UDC_2", "IDC_2"]
from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) =>
    r._measurement == "CommonInverterData" and contains(value: r._field, set: fields))
  |> aggregateWindow(every: 1m, fn: mean)
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with PDC_SW: r.IDC * r.UDC, PDC_NE: r.IDC_2 * r.UDC_2}))
  |> map(fn: (r) => ({r with PDC_tot: r.PDC_SW + r.PDC_NE}))
  |> keep(columns: ["_time", "PDC_SW", "PDC_NE", "PDC_tot"])