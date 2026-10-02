# Round 19 test cars

Baseline is round 18's Hub Fix 15 (Combined max). This round re-cut the body panels
along the RB14's real panel lines (with lips on every cut edge), made the DRS flap a
hinged part of its own, and moved the halo into its own part. In the game: *Test N · ...*.

| # | Car | Change |
|---|---|---|
| 1 | No halo | Baseline (round 18's Hub Fix 15) without the halo: its part (mesh, 6 kg of nodes, beams and collision triangles) left off |

Offline checks: stiffness = highest omega*dt (target <= 1.72), damped = with
damping (<= 1.85), corner = wheel-corner modes with damping (<= 1.82; round 10
was 1.78 and fine, round 11 1.83 and broke), tyres = stiffness per kg vs the F4's (<= 1).

| Car | Tries | stiffness | damped | corner | tyres | spawns? | judder? |
|---|---|---|---|---|---|---|---|
| `test_01` No halo | Baseline (round 18's Hub Fix 15) without the halo: its part (mesh, 6 kg of nodes, beams and collision triangles) left off | 1.72 | 1.82 | 1.82 | 0.69 | | |
