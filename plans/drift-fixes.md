# Drift-fix test cars (round 17)

The problem: after a hard turn, with the steering centred, the car keeps turning
the other way for ~2.5-4.5 s. In the round-16 replays the inner rear wheel loses
~3 deg of toe-in in the turn and holds it ~1.5-2 s after the steering is centred;
nothing in the offline model explains it. Baseline is round 16's Test 05 (engine
+12 %). Every car now carries virtual sensors (lua/controller/redbullSensors.lua)
recorded in replays; each fix below targets one suspect and names the sensors that
show whether it moved. In the game: *Drift Fix N · ...*.

Test drive per car (one short replay, ~1 min, big open area): three hard left turns
at speed, each followed by straightening up and holding the wheel centred 5-6 s;
then three hard right turns the same way. Then `python3 tools/rb14/replay_analysis.py
<replay>` -- its SENSORS section lists, per turn, the inner rear wheel's sensors
that are still off while the car drifts.

| # | Fix | Suspect / change | Sensors |
|---|---|---|---|
| 1 | Stiff rear hubs | the hub shifting on its upright: rear hub toe torsion bar 5x (the most the gates allow) | sn_R?_hub_* (axle node to upright distances), sn_R?_toe |
| 2 | Stiffer rear links | the six upright-to-gearbox links stretching: 1.2x stiffer (1.5x goes over the solver limits) | sn_R?_link_* |
| 3 | Driveshaft play | the driveshaft end stops pushing the inner axle node: 3x the plunge before the stops (+-15 % of its length) | sn_R?_shaft (base stops at +-33 mm) |
| 4 | Rear droop room | the unloaded inner wheel reaching its droop stop: 2x the droop travel | sn_R?_spring, sn_R?_in_z / out_z |
| 5 | Gearbox torque reaction | the drive-torque reaction pushing the axle: reaction on the wheel's own side of the gearbox (Rear Fix 3's part) | sn_R?_in_y / out_y (fore-aft), sn_R?_toe |
| 6 | Rear toe reset | the 3-4 deg rear toe-in itself: toe / camber links reset for ~0.3 deg per side | sn_R?_toe at rest and on the straights |
| 7 | All drift fixes | 1-6 together (hub torsion 4x) | all |

Offline checks: stiffness = highest omega*dt (target <= 1.67), damped = with
damping (<= 1.85), corner = wheel-corner modes with damping (<= 1.82; round 10
was 1.78 and fine, round 11 1.83 and broke), tyres = stiffness per kg vs the F4's (<= 1).

| Car | Tries | stiffness | damped | corner | tyres | spawns? | judder? |
|---|---|---|---|---|---|---|---|
| `drift_01` Stiff rear hubs | the hub shifting on its upright: rear hub toe torsion bar 5x (the most the gates allow); check: sn_R?_hub_* (axle node to upright distances), sn_R?_toe | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `drift_02` Stiffer rear links | the six upright-to-gearbox links stretching: 1.2x stiffer (1.5x goes over the solver limits); check: sn_R?_link_* | 1.67 | 1.82 | 1.78 | 0.69 | | |
| `drift_03` Driveshaft play | the driveshaft end stops pushing the inner axle node: 3x the plunge before the stops (+-15 % of its length); check: sn_R?_shaft (base stops at +-33 mm) | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `drift_04` Rear droop room | the unloaded inner wheel reaching its droop stop: 2x the droop travel; check: sn_R?_spring, sn_R?_in_z / out_z | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `drift_05` Gearbox torque reaction | the drive-torque reaction pushing the axle: reaction on the wheel's own side of the gearbox (Rear Fix 3's part); check: sn_R?_in_y / out_y (fore-aft), sn_R?_toe | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `drift_06` Rear toe reset | the 3-4 deg rear toe-in itself: toe / camber links reset for ~0.3 deg per side; check: sn_R?_toe at rest and on the straights | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `drift_07` All drift fixes | 1-6 together (hub torsion 4x) | 1.67 | 1.82 | 1.78 | 0.69 | | |
