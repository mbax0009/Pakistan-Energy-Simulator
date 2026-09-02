# Wind turbine reference data

`IEA_Reference_3.4MW_130.csv` is copied without modification from the
National Laboratory of the Rockies Wind Turbine Power Curve Archive:

https://github.com/NatLabRockies/turbine-models/blob/main/turbine_models/data/Onshore/IEA_Reference_3.4MW_130.csv

The upstream archive is licensed under the BSD 3-Clause License. The simulator uses
the tabulated electrical-power column as its default wind-generation curve, with
linear interpolation between points. The legacy cubic approximation is retained only
as an explicit fallback when no turbine curve is selected.
