# Hub-fix test cars (round 18)

The problem: after a hard turn, with the steering centred, the car keeps turning
the other way for ~2.5-5 s. The round-17 sensors (replayTurns, Baseline) show why:
the rear toe follows the rear axle height at ~0.17 deg per mm (the offline model:
0.007), because the axle nodes shift 2-4 mm on the upright as the wheel compresses;
after a turn the inner wheel's toe lags its height ~1-1.5 s, 0.6-0.8 deg of net rear
steer. These cars stiffen the hub on the upright three ways, each in graded steps:
the axle beams themselves, new bracing (two nodes on each upright, ahead of and
behind the axle, braced to both axle nodes) and a toe brace (torsion bar). The
stiffer steps need more mass at the rear corner to stay under the 2 kHz solver
limit; it comes out of the engine ballast (same total weight), and car 12 has the
mass alone as a control. Baseline is unchanged except for the brace nodes (+3 kg per
rear corner, unbraced, taken from the ballast). In the game: *Hub Fix N · ...*.

Test drive per car (one short replay): three hard left turns at speed, each followed
by straightening up and holding the wheel centred 5-6 s; then three hard right turns.
Then `python3 tools/rb14/replay_analysis.py <replay>`: the SENSORS section gives the
hub_* movement and the toe vs in_z slope (Baseline ~0.17 deg/mm); a fix that works
brings both down and the post-turn yaw with them.

| # | Fix | Change |
|---|---|---|
| 1 | Axle beams 1.25x | the 8 axle-node-to-upright beams 1.25x stiffer |
| 2 | Axle beams 1.5x | axle beams 1.5x (+4 kg per rear corner, from the engine ballast, to stay stable) |
| 3 | Axle beams 2x | axle beams 2x (+8 kg per rear corner) |
| 4 | Axle beams 2.5x | axle beams 2.5x (+12 kg per rear corner; just over the stiffness target) |
| 5 | Hub bracing 0.5 | brace beams from new nodes ahead of / behind the axle on the upright to both axle nodes, at 0.5x the upright-link stiffness |
| 6 | Hub bracing 1 | bracing at 1x (+6 kg per rear corner) |
| 7 | Hub bracing 1.5 | bracing at 1.5x (+10 kg per rear corner) |
| 8 | Hub bracing 2 | bracing at 2x (+12 kg per rear corner; just over the stiffness target) |
| 9 | Toe brace 200k | torsion bar holding the outer axle node against toe about the upright, 200 kNm/rad |
| 10 | Toe brace 400k | toe brace 400 kNm/rad |
| 11 | Toe brace 600k | toe brace 600 kNm/rad (+8 kg per rear corner; just over the stiffness target) |
| 12 | Corner mass only | control: +12 kg per rear corner and nothing else (to tell the mass from the fixes) |
| 13 | Combined medium | axle beams 1.5x + bracing 1 + toe brace 400k (+8 kg per corner) |
| 14 | Combined strong | axle beams 2x + bracing 1 + toe brace 400k (+12 kg per corner) |
| 15 | Combined max | axle beams 2x + bracing 1.5 + toe brace 600k (+12 kg per corner; over the stiffness target) |
| 16 | Strong + more toe-in | Combined strong with ~0.6 deg more static rear toe-in (offline model), in case the stiffer hub takes away the toe-in the soft hub gave at rest |
| 17 | More rear toe-in | static rear toe-in only: ~0.6 deg more per side (offline model) |
| 18 | Less rear toe-in | static rear toe-in only: ~0.6 deg less per side (offline model) |

Offline checks: stiffness = highest omega*dt (target <= 1.67), damped = with
damping (<= 1.85), corner = wheel-corner modes with damping (<= 1.82; round 10
was 1.78 and fine, round 11 1.83 and broke), tyres = stiffness per kg vs the F4's (<= 1).

| Car | Tries | stiffness | damped | corner | tyres | spawns? | judder? |
|---|---|---|---|---|---|---|---|
| `hub_01` Axle beams 1.25x | the 8 axle-node-to-upright beams 1.25x stiffer; check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.80 | 0.69 | | |
| `hub_02` Axle beams 1.5x | axle beams 1.5x (+4 kg per rear corner, from the engine ballast, to stay stable); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `hub_03` Axle beams 2x | axle beams 2x (+8 kg per rear corner); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.79 | 0.69 | | |
| `hub_04` Axle beams 2.5x | axle beams 2.5x (+12 kg per rear corner; just over the stiffness target); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.69 | 1.82 | 1.82 | 0.69 | | |
| `hub_05` Hub bracing 0.5 | brace beams from new nodes ahead of / behind the axle on the upright to both axle nodes, at 0.5x the upright-link stiffness; check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.79 | 0.69 | | |
| `hub_06` Hub bracing 1 | bracing at 1x (+6 kg per rear corner); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `hub_07` Hub bracing 1.5 | bracing at 1.5x (+10 kg per rear corner); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `hub_08` Hub bracing 2 | bracing at 2x (+12 kg per rear corner; just over the stiffness target); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.68 | 1.82 | 1.80 | 0.69 | | |
| `hub_09` Toe brace 200k | torsion bar holding the outer axle node against toe about the upright, 200 kNm/rad; check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `hub_10` Toe brace 400k | toe brace 400 kNm/rad; check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `hub_11` Toe brace 600k | toe brace 600 kNm/rad (+8 kg per rear corner; just over the stiffness target); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.68 | 1.82 | 1.77 | 0.69 | | |
| `hub_12` Corner mass only | control: +12 kg per rear corner and nothing else (to tell the mass from the fixes); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `hub_13` Combined medium | axle beams 1.5x + bracing 1 + toe brace 400k (+8 kg per corner); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `hub_14` Combined strong | axle beams 2x + bracing 1 + toe brace 400k (+12 kg per corner); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `hub_15` Combined max | axle beams 2x + bracing 1.5 + toe brace 600k (+12 kg per corner; over the stiffness target); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `hub_16` Strong + more toe-in | Combined strong with ~0.6 deg more static rear toe-in (offline model), in case the stiffer hub takes away the toe-in the soft hub gave at rest; check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `hub_17` More rear toe-in | static rear toe-in only: ~0.6 deg more per side (offline model); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
| `hub_18` Less rear toe-in | static rear toe-in only: ~0.6 deg less per side (offline model); check: sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section | 1.67 | 1.82 | 1.77 | 0.69 | | |
