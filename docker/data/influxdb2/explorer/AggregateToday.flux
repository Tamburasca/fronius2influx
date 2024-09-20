//
// AggregateToday
//

import "internal/debug"
import "experimental"
import "timezone"

option location = timezone.location(name: "Europe/Berlin")

ReLU = (x) => if exists x then
                if x > 0.0 then x
                else 0.0
              else debug.null(type: "float")
multByX = (tables=<-, x) =>
    tables
        |> map(fn: (r) => ({r with _value: r._value * x}))
divByX = (tables=<-, x) =>
    tables
        |> map(fn: (r) => ({r with _value: r._value / x}))
fieldsCommon = ["UDC", "IDC", "UDC_2", "IDC_2", "PAC"]
RES = 60 // time resolution

from(bucket: "Fronius")
//  |> range(start: today())
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) => (r["_measurement"] == "Battery" and (r["_field"] == "Voltage_DC" or r["_field"] == "Current_DC")) or
                       (r["_measurement"] == "CommonInverterData" and contains(value: r._field, set: fieldsCommon)) or
                       (r["_measurement"] == "SmartMeter" and r["_field"] == "PowerReal_P_Sum")
    )
  |> aggregateWindow(every: duration(v: RES * 1000000000), fn: mean) // duration results ns
  |> pivot(rowKey: ["_time"], columnKey: ["_field", "_measurement"], valueColumn: "_value")
  |> rename(columns: {
    PowerReal_P_Sum_SmartMeter: "PowerNet",
    PAC_CommonInverterData: "PowerAC"
    })
  |> map(fn: (r) => ({r with PowerSolarDC: r.IDC_CommonInverterData * r.UDC_CommonInverterData
                                           + r.IDC_2_CommonInverterData * r.UDC_2_CommonInverterData,
//                             PowerConsumed: r.PowerAC
//                                            + r.PowerNet,
                             NetFrom: ReLU(x: r.PowerNet),
                             NetTo: ReLU(x: -r.PowerNet),
                             BatteryCharged: ReLU(x: r.Voltage_DC_Battery * r.Current_DC_Battery),
                             BatteryDischarged: ReLU(x: -r.Voltage_DC_Battery * r.Current_DC_Battery)
  }))
  |> map(fn: (r) => ({r with UsageIn: r.PowerSolarDC
                                      - r.NetTo,
                             UsageDirect: r.PowerSolarDC
                                          - r.NetTo
                                          - r.BatteryCharged
  }))
  |> map(fn: (r) => ({r with ProdIn: r.UsageDirect
                                     + r.BatteryDischarged,
                             PowerConsumed: r.UsageDirect
                                            + r.BatteryDischarged
                                            + r.NetFrom
  }))
  |> keep(columns:["_time",
                   "PowerSolarDC",
                   "PowerConsumed",
                   "NetFrom",
                   "NetTo",
                   "BatteryCharged",
                   "BatteryDischarged",
                   "UsageIn",
                   "UsageDirect",
                   "ProdIn"
                   ])
  |> experimental.unpivot()
  |> cumulativeSum()
  |> divByX(x: 3600000.0 / float(v: RES))
  |> yield()