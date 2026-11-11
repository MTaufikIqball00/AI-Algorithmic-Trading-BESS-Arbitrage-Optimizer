"""
Solar PV Data Dictionary & Governance Specification.
Defines every expected field, meaning, unit, datatype, validity constraints, and missing-value policies.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple


class DataQualityFlag(str, Enum):
    VALID = "VALID"
    INTERPOLATED = "INTERPOLATED"
    CAPPED = "CAPPED"
    MISSING = "MISSING"
    SUSPECT = "SUSPECT"
    STALE = "STALE"
    SYNTHETIC = "SYNTHETIC"


class InverterStatus(str, Enum):
    OPERATING_NORMAL = "OPERATING_NORMAL"
    DERATED_CURTAILED = "DERATED_CURTAILED"
    FAULT_TRIPPED = "FAULT_TRIPPED"
    STANDBY_NIGHT = "STANDBY_NIGHT"
    OFFLINE_MAINTENANCE = "OFFLINE_MAINTENANCE"
    UNKNOWN = "UNKNOWN"


class SensorStatus(str, Enum):
    NORMAL = "NORMAL"
    STUCK = "STUCK"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    DISCONNECTED = "DISCONNECTED"
    UNCALIBRATED = "UNCALIBRATED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FieldDefinition:
    name: str
    meaning: str
    unit: str
    data_type: str
    source: str
    is_required: bool
    min_value: Optional[float]
    max_value: Optional[float]
    missing_value_policy: str
    scientific_rationale: str


DATA_DICTIONARY: Dict[str, FieldDefinition] = {
    "timestamp": FieldDefinition(
        name="timestamp",
        meaning="UTC or ISO-8601 string marking beginning of measurement interval",
        unit="ISO 8601 string",
        data_type="datetime64[ns, UTC] or str",
        source="Datalogger / SCADA / Inverter telemetry",
        is_required=True,
        min_value=None,
        max_value=None,
        missing_value_policy="Strictly reject row; timestamps cannot be synthesized without temporal alignment.",
        scientific_rationale="Monotonic chronological ordering is foundational for zero-lookahead time-series analysis.",
    ),
    "panel_id": FieldDefinition(
        name="panel_id",
        meaning="Identifier for physical PV string, module, or inverter sub-array",
        unit="dimensionless",
        data_type="str",
        source="SCADA Asset Hierarchy",
        is_required=False,
        min_value=None,
        max_value=None,
        missing_value_policy="Default to 'default_array' when single-asset installation.",
        scientific_rationale="Required for panel-to-panel degradation and anomaly comparison.",
    ),
    "irradiance": FieldDefinition(
        name="irradiance",
        meaning="Global Horizontal Irradiance (GHI) or uncalibrated global sunlight flux",
        unit="W/m^2",
        data_type="float64",
        source="Pyranometer / Weather Station",
        is_required=False,
        min_value=0.0,
        max_value=1500.0,
        missing_value_policy="Time-aware linear interpolation for gaps <= 15 min; mark MISSING for long gaps. Nighttime clamped to 0.",
        scientific_rationale="Solar irradiance is bounded by solar constant (~1361 W/m^2) plus atmospheric lensing (~1500 W/m^2 max).",
    ),
    "plane_of_array_irradiance": FieldDefinition(
        name="plane_of_array_irradiance",
        meaning="Direct and diffuse solar radiation incident on the tilted collector surface (POA)",
        unit="W/m^2",
        data_type="float64",
        source="Reference Cell / Tilted Pyranometer",
        is_required=False,
        min_value=0.0,
        max_value=1500.0,
        missing_value_policy="Calculate from GHI via transposition models or flag MISSING. Do not equate directly to GHI without conversion.",
        scientific_rationale="POA irradiance determines the photon flux absorbed by the photovoltaic semiconductor junction.",
    ),
    "panel_temperature": FieldDefinition(
        name="panel_temperature",
        meaning="Back-of-module or photovoltaic cell operating temperature",
        unit="deg C",
        data_type="float64",
        source="RTD / Thermocouple adhered to panel backsheet",
        is_required=False,
        min_value=-40.0,
        max_value=95.0,
        missing_value_policy="Estimate via King / Sandia thermal model from ambient temp and irradiance, or flag INTERPOLATED.",
        scientific_rationale="PV cell efficiency decreases with temperature by approx -0.35% to -0.45% per deg C above STC (25 deg C).",
    ),
    "ambient_temperature": FieldDefinition(
        name="ambient_temperature",
        meaning="Dry-bulb outdoor air temperature in the shade",
        unit="deg C",
        data_type="float64",
        source="Weather Station / On-site meteorological sensor",
        is_required=False,
        min_value=-40.0,
        max_value=60.0,
        missing_value_policy="Linear interpolation for gaps <= 30 min; regional weather forecast fallback.",
        scientific_rationale="Governs convective heat loss and thermal equilibrium of solar cells and inverters.",
    ),
    "voltage": FieldDefinition(
        name="voltage",
        meaning="Direct Current (DC) string voltage or Alternating Current (AC) inverter output voltage",
        unit="V",
        data_type="float64",
        source="Inverter MPPT Tracker / DC Combiner Box",
        is_required=False,
        min_value=0.0,
        max_value=1500.0,
        missing_value_policy="Mark SUSPECT if non-zero at nighttime; flag MISSING if disconnected.",
        scientific_rationale="DC operating voltage is controlled by MPPT tracking between open circuit Voc and maximum power Vmp.",
    ),
    "current": FieldDefinition(
        name="current",
        meaning="Direct Current (DC) string amperage or Alternating Current (AC) phase current",
        unit="A",
        data_type="float64",
        source="Hall-effect current sensor / Shunt resistor",
        is_required=False,
        min_value=0.0,
        max_value=1000.0,
        missing_value_policy="Clamped to 0 at night; flag SUSPECT if negative in pure DC strings.",
        scientific_rationale="DC current is proportional to absorbed photon flux and active irradiance.",
    ),
    "power": FieldDefinition(
        name="power",
        meaning="Active electrical power generation (DC or AC, specified by metadata)",
        unit="kW",
        data_type="float64",
        source="Power meter / Inverter telemetry",
        is_required=True,
        min_value=0.0,
        max_value=100000.0,
        missing_value_policy="Calculate from V * I if synchronized, or persist historical roll, flag quality status.",
        scientific_rationale="Primary dispatch and forecasting target variable. Nighttime baseline is strictly 0.0 kW.",
    ),
    "energy": FieldDefinition(
        name="energy",
        meaning="Integrated active electrical energy production over time interval or cumulative meter reading",
        unit="kWh",
        data_type="float64",
        source="Revenue Meter / Datalogger Accumulator",
        is_required=False,
        min_value=0.0,
        max_value=1e9,
        missing_value_policy="Integrate power using trapezoidal or rectangular numerical integration over interval dt.",
        scientific_rationale="Energy is the time integral of power: E = \\int P(t) dt.",
    ),
    "humidity": FieldDefinition(
        name="humidity",
        meaning="Relative atmospheric humidity",
        unit="%",
        data_type="float64",
        source="Hygrometer",
        is_required=False,
        min_value=0.0,
        max_value=100.0,
        missing_value_policy="Fill with 50.0% nominal or interpolate short gaps.",
        scientific_rationale="High humidity correlates with atmospheric water vapor scattering and condensation/dew.",
    ),
    "wind_speed": FieldDefinition(
        name="wind_speed",
        meaning="Horizontal wind speed at array height",
        unit="m/s",
        data_type="float64",
        source="Anemometer",
        is_required=False,
        min_value=0.0,
        max_value=55.0,
        missing_value_policy="Fill with 1.0 m/s calm baseline.",
        scientific_rationale="Wind drives forced convective cooling of modules, decreasing cell temp and boosting efficiency.",
    ),
    "cloud_cover": FieldDefinition(
        name="cloud_cover",
        meaning="Total sky cloud cover fraction",
        unit="fraction 0.0 to 1.0 or %",
        data_type="float64",
        source="Satellite / Sky imager / Numerical Weather Prediction",
        is_required=False,
        min_value=0.0,
        max_value=100.0,
        missing_value_policy="Set to 0.0 (clear sky assumption) if absent, or retrieve from NWP model.",
        scientific_rationale="Cloud cover modulates direct solar attenuation and diffuse sky fraction.",
    ),
    "precipitation": FieldDefinition(
        name="precipitation",
        meaning="Liquid precipitation rate or cumulative rainfall",
        unit="mm/hr or mm",
        data_type="float64",
        source="Tipping bucket rain gauge",
        is_required=False,
        min_value=0.0,
        max_value=250.0,
        missing_value_policy="Default to 0.0 mm.",
        scientific_rationale="Crucial evidence variable for soiling wash-off events vs dust accumulation.",
    ),
    "inverter_status": FieldDefinition(
        name="inverter_status",
        meaning="Discrete operating state code of the PV central or string inverter",
        unit="categorical string",
        data_type="str",
        source="Inverter Modbus / SunSpec registers",
        is_required=False,
        min_value=None,
        max_value=None,
        missing_value_policy="Default to 'UNKNOWN' if telemetry absent.",
        scientific_rationale="Identifies curtailment, tripping, thermal derating vs panel soiling.",
    ),
    "sensor_status": FieldDefinition(
        name="sensor_status",
        meaning="Health indicator of the primary monitoring instruments",
        unit="categorical string",
        data_type="str",
        source="SCADA sensor diagnostic bitmask",
        is_required=False,
        min_value=None,
        max_value=None,
        missing_value_policy="Default to 'UNKNOWN' if telemetry absent.",
        scientific_rationale="Prevents diagnosing sensor failure or frozen telemetry as a solar equipment anomaly.",
    ),
    "maintenance_timestamp": FieldDefinition(
        name="maintenance_timestamp",
        meaning="Documented timestamp of field service, component replacement, or inverter repair",
        unit="ISO 8601 string",
        data_type="str",
        source="Computerized Maintenance Management System (CMMS)",
        is_required=False,
        min_value=None,
        max_value=None,
        missing_value_policy="None if no maintenance occurred.",
        scientific_rationale="Ground truth for validating predictive maintenance recommendations.",
    ),
    "cleaning_timestamp": FieldDefinition(
        name="cleaning_timestamp",
        meaning="Documented timestamp of manual or robotic panel washing",
        unit="ISO 8601 string",
        data_type="str",
        source="O&M Log / Field Dispatch Record",
        is_required=False,
        min_value=None,
        max_value=None,
        missing_value_policy="None if no cleaning event is logged.",
        scientific_rationale="Essential boundary condition for quantifying soiling ratio recovery.",
    ),
}
