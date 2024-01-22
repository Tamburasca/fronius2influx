//
// Power Total Live
//
import "internal/debug"
fieldsCommon = ["UDC", "IDC", "UDC_2", "IDC_2", "PAC"]
fieldsBattery = ["Voltage_DC", "Current_DC", "StateOfCharge_Relative"]
rES = 6 // time resolution (s)

from(bucket: "Fronius")
  |> range(start: v.timeRangeStart, stop:v.timeRangeStop)
  |> filter(fn: (r) => (r["_measurement"] == "Battery" and contains(value: r._field, set: fieldsBattery)) or
                       (r["_measurement"] == "CommonInverterData" and contains(value: r._field, set: fieldsCommon)) or
                       (r["_measurement"] == "SmartMeter" and r["_field"] == "PowerReal_P_Sum")
    )
  |> aggregateWindow(every: duration(v: rES * 1000000000), fn: mean) // duration return ns
  |> pivot(rowKey: ["_time"], columnKey: ["_field", "_measurement"], valueColumn: "_value")
  |> rename(columns: {
    PowerReal_P_Sum_SmartMeter: "PowerNet",
    PAC_CommonInverterData: "PowerAC",
    StateOfCharge_Relative_Battery: "BatteryLoadingLevel"
    })
  |> map(fn: (r) => ({r with PowerBattery: -r.Voltage_DC_Battery * r.Current_DC_Battery,
                             PowerSolarDC: r.IDC_CommonInverterData * r.UDC_CommonInverterData
                                           + r.IDC_2_CommonInverterData * r.UDC_2_CommonInverterData,
                             PowerConsumed: r.PowerAC
                                            + r.PowerNet
    }))
  |> keep(columns:["_time",
                   "PowerSolarDC",
                   "PowerConsumed",
                   "PowerNet",
                   "PowerBattery",
                   "BatteryLoadingLevel"])
