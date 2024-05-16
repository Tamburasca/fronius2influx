//
// Power Current
//

import "experimental"
import "math"
import "date"
import "strings"

ReLU = (x) => if x > 0.0 then x else 0.0

fieldsCommon = ["UDC", "IDC", "UDC_2", "IDC_2", "PAC"]
fieldsBattery = ["Voltage_DC", "Current_DC", "StateOfCharge_Relative"]
rES = 6 // time to aggregate over (s), duration returns ns

basic = from(bucket: "Fronius")
  |> range(start: -1m, stop: date.truncate(t: now(), unit: duration(v: rES * 1000000000)))
  |> filter(fn: (r) => (r["_measurement"] == "Battery" and contains(value: r._field, set: fieldsBattery)) or
                       (r["_measurement"] == "CommonInverterData" and contains(value: r._field, set: fieldsCommon)) or
                       (r["_measurement"] == "SmartMeter" and r["_field"] == "PowerReal_P_Sum")
    )
  |> aggregateWindow(every: duration(v: rES * 1000000000), fn: last, createEmpty: false)
  |> last()
  |> pivot(rowKey: ["_time"], columnKey: ["_field", "_measurement"], valueColumn: "_value")
  |> rename(columns: {
    PowerReal_P_Sum_SmartMeter: "PowerNet",
    PAC_CommonInverterData: "PowerAC",
    StateOfCharge_Relative_Battery: "Battery Loading Level"
    })
  |> map(fn: (r) => ({r with PowerBattery: -r.Voltage_DC_Battery * r.Current_DC_Battery,
                             SolarDC: r.IDC_CommonInverterData * r.UDC_CommonInverterData
                                      + r.IDC_2_CommonInverterData * r.UDC_2_CommonInverterData,
                             Consumed: ReLU(x: r.PowerAC
                                       + r.PowerNet)
    }))
  |> keep(columns:["_time",
                   "SolarDC",
                   "Consumed",
                   "PowerNet",
                   "PowerBattery",
                   "Battery Loading Level"])
  |> experimental.unpivot()

basic
  |> map(fn: (r) => ({r with _value: math.trunc(x: r._value)}))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field,
    u: if r._field == "PowerBattery" and r._value <= 0. then "Battery Charging" else "Battery Discharging",
    t: "PowerBattery")}))
  |> map(fn: (r) => ({r with _field: strings.replaceAll(v: r._field,
    u: if r._field == "PowerNet" and r._value <= 0. then "Net To" else "Net From",
    t: "PowerNet")}))
  |> map(fn: (r) => ({r with _value: if r._field == "Battery Charging" then math.abs(x: r._value) else r._value}))
  |> map(fn: (r) => ({r with _value: if r._field == "Net To" then math.abs(x: r._value) else r._value}))
  |> yield()