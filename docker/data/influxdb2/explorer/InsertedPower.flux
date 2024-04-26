import "strings"
import "experimental"
import "timezone"

option location = timezone.location(name: "Europe/Berlin")

fields1 = ["UDC", "IDC", "UDC_2", "IDC_2"]
LIMIT_INCIDENCE = 0.087 // corresponds to >5 degree incidence angle
rES = 6 // time resolution

inserted = from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) =>
    r._measurement == "CommonInverterData" and contains(value: r._field, set: fields1))
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with PDC_SW: r.IDC * r.UDC,
                             PDC_NE: r.IDC_2 * r.UDC_2,
                             PDC_TOT: r.PDC_NE + r.PDC_SW}))
  |> map(fn: (r) => ({r with PDC_TOT: r.PDC_NE + r.PDC_SW}))
  |> keep(columns: ["_time", "PDC_SW", "PDC_NE", "PDC_TOT"])
  |> experimental.unpivot()

fields2 = ["1_intensity_corr_area_eff", "1_incidence_ratio", "2_intensity_corr_area_eff", "2_incidence_ratio"]
solar = from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) =>
    r._measurement == "SolarData" and contains(value: r._field, set: fields2))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field, t: "1_intensity_corr_area_eff", u: "Intensity_SW")}))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field, t: "2_intensity_corr_area_eff", u: "Intensity_NE")}))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field, t: "1_incidence_ratio", u: "IncidenceRatio_SW")}))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field, t: "2_incidence_ratio", u: "IncidenceRatio_NE")}))
  |> drop(columns: ["_measurement"])

combine = union(tables: [solar, inserted])
  |> aggregateWindow(every: duration(v: rES * 1000000000), fn: mean) // duration results ns
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with
                      diffuse_SW: if r.IncidenceRatio_SW < LIMIT_INCIDENCE then r.PDC_SW / r.Intensity_SW
                      else  r.PDC_SW / (r.IncidenceRatio_SW * r.Intensity_SW),
                      diffuse_NE: if r.IncidenceRatio_NE < LIMIT_INCIDENCE then r.PDC_NE / r.Intensity_NE
                      else  r.PDC_NE / (r.IncidenceRatio_NE * r.Intensity_NE),
                      Intensity_SW: if r.IncidenceRatio_SW < LIMIT_INCIDENCE then 0.
                      else r.IncidenceRatio_SW * r.Intensity_SW,
                      Intensity_NE: if r.IncidenceRatio_NE < LIMIT_INCIDENCE then 0.
                      else r.IncidenceRatio_NE * r.Intensity_NE
                      }))
  |> drop(columns: ["_start", "_stop", "IncidenceRatio_NE", "IncidenceRatio_SW"])
  |> yield()