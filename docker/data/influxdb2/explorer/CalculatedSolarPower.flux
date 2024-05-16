//
// Calculated Solar Power
//

import "strings"
import "math"
fields = ["1_intensity_corr_area_eff", "1_incidence_ratio", "2_intensity_corr_area_eff", "2_incidence_ratio"]

from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) =>
    r._measurement == "SolarData" and contains(value: r._field, set: fields)
  )
  |> aggregateWindow(every: 1m, fn: mean)
//  |> map(fn: (r) => ({r with _value: if r._field == "1_incidence_ratio" or r._field == "2_incidence_ratio"
//    then
//      if exists r._value then math.asin(x: r._value) * 180. / math.pi else 0.
//    else
//      r._value}))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field, t: "1_intensity_corr_area_eff", u: "Intensity_SW")}))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field, t: "2_intensity_corr_area_eff", u: "Intensity_NE")}))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field, t: "1_incidence_ratio", u: "Incidence_SW")}))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field, t: "2_incidence_ratio", u: "Incidence_NE")}))
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with
    Intens_correct_SW: r.Intensity_SW * r.Incidence_SW,
    Intens_correct_NE: r.Intensity_NE * r.Incidence_NE
    }))
  |> keep(columns: ["_time", "Intensity_SW", "Intensity_NE", "Incidence_SW", "Incidence_NE", "Intens_correct_SW", "Intens_correct_NE"])