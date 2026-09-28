-- Offline checks for the redbull mod's Lua controllers, with the parts of
-- BeamNG's vehicle Lua they use stubbed out (electrics, guihooks, obj, v, log,
-- vec3). Not a substitute for the game; it catches logic and runtime errors.
--
--     luajit tools/rb14/test_controllers.lua        (from the repo root)

package.path = "vehicles/redbull/lua/controller/?.lua;" .. package.path

-- ------------------------------------------------------------ stubs
electrics = {values = {}}
guihooks = {message = function(m) print("   [ui] " .. m.txt) end}
function log(level, tag, msg) print("   [" .. level .. "] " .. tag .. ": " .. msg) end

local V = {}
V.__index = V
function vec3(x, y, z) return setmetatable({x = x, y = y, z = z}, V) end
V.__add = function(a, b) return vec3(a.x + b.x, a.y + b.y, a.z + b.z) end
V.__sub = function(a, b) return vec3(a.x - b.x, a.y - b.y, a.z - b.z) end
V.__mul = function(a, s) return vec3(a.x * s, a.y * s, a.z * s) end
function V:dot(b) return self.x * b.x + self.y * b.y + self.z * b.z end
function V:cross(b) return vec3(self.y * b.z - self.z * b.y, self.z * b.x - self.x * b.z, self.x * b.y - self.y * b.x) end
function V:normalized() local l = math.sqrt(self:dot(self)); return self * (1 / l) end

local failures = 0
local function check(cond, what)
  print((cond and "  ok   " or "  FAIL ") .. what)
  if not cond then failures = failures + 1 end
end

local function run(ctrl, seconds, dt)
  for _ = 1, math.floor(seconds / dt + 0.5) do ctrl.updateGFX(dt) end
end

-- ------------------------------------------------------------ ERS
print("redbullERS")
local ers = require("redbullERS")
local ice = {{0, 0}, {1000, 150}, {6000, 450}, {10500, 505}, {12000, 440}, {14000, 240}}
ers.init({deployKW = 120, maxTorque = 180, storeMJ = 4.0, mguhKW = 40, harvestKW = 120, iceTorque = ice})
local e = electrics.values
check(math.abs(e.ersSOC - 100) < 1e-6, "starts with a full store")

-- full throttle at 11,000 rpm: deploys, throttle left alone
e.throttle, e.brake, e.rpm, e.wheelspeed = 1, 0, 11000, 60
ers.updateGFX(0.02)
check(e.ersDeploy == 1 and e.throttle == 1, "deploys at full throttle")
-- drain: 120 kW from 4 MJ, less MGU-H 40 kW * 0.9 -> ~48 s
local t = 0
while e.ersSOC > 25.5 and t < 200 do e.throttle = 1; ers.updateGFX(0.05); t = t + 0.05 end
check(t > 25 and t < 60, string.format("balanced mode deploys for %.0f s before holding the 25 %% reserve", t))
local soc0 = e.ersSOC
local av = 11000 * math.pi / 30
local iceT = 505 + (440 - 505) * (500 / 1500)
local ersT = math.min(180, 120000 / av)
local capIce = iceT / (iceT + ersT)
local caps = {}
for k = 1, 40 do e.throttle = 1; ers.updateGFX(0.05); caps[k] = e.throttle end
check(math.abs(caps[40] - caps[39]) < 1e-9 and caps[40] > capIce and caps[40] < 1,
      string.format("at the reserve: steady throttle %.3f (ICE share %.3f + MGU-H-fed deploy), no toggling", caps[40], capIce))
check(math.abs(e.ersSOC - soc0) < 1, string.format("store holds at the reserve (%.1f %% -> %.1f %%)", soc0, e.ersSOC))
-- lifting below 9000 rpm: no MGU-H, so the cap drops to the ICE share
e.rpm = 8000
e.throttle = 1
ers.updateGFX(0.05)
local iceT8 = 450 + (505 - 450) * (2000 / 4500)   -- the test curve above at 8000 rpm
local ersT8 = math.min(180, 120000 / (8000 * math.pi / 30))
check(math.abs(e.throttle - iceT8 / (iceT8 + ersT8)) < 1e-6, "below the MGU-H band the reserve caps to the ICE share")
e.rpm = 11000
-- part throttle below the cap is never touched
e.throttle = 0.5
ers.updateGFX(0.05)
check(e.throttle == 0.5, "part throttle passes through")
-- braking at speed harvests
local before = e.ersSOC
e.throttle, e.brake, e.wheelspeed, e.rpm = 0, 1, 60, 9000
run(ers, 2, 0.05)
check(e.ersSOC > before + 4, string.format("2 s of hard braking harvests %.1f %%", e.ersSOC - before))
-- harvest mode never deploys
e.ersMode = 0
e.throttle, e.brake, e.rpm = 1, 0, 11000
ers.updateGFX(0.05)
check(e.ersDeploy == 0 and e.throttle < 1, "harvest mode caps the throttle")
-- overtake mode deploys below the reserve
e.ersMode = 2
e.throttle = 1
ers.updateGFX(0.05)
check(e.ersDeploy == 1, "overtake mode deploys")
ers.reset()
check(math.abs(e.ersSOC - 100) < 1e-6, "reset refills the store")

-- ------------------------------------------------------------ DRS
print("redbullDRS")
electrics.values = {}
e = electrics.values
local drs = require("redbullDRS")
drs.init({minSpeed = 20})
e.wheelspeed, e.brake = 10, 0
e.drsRequest = 1
drs.updateGFX(0.02)
check(e.drs == 0, "stays shut below minSpeed")
e.wheelspeed = 70
drs.updateGFX(0.02)
check(e.drs == 1, "opens on request at speed")
e.brake = 0.3
drs.updateGFX(0.02)
check(e.drs == 0 and e.drsRequest == 0, "closes and clears the request on braking")
e.brake = 0
drs.updateGFX(0.02)
check(e.drs == 0, "stays shut until requested again")

-- ------------------------------------------------------------ ground effect
print("redbullGroundEffect")
electrics.values = {}
e = electrics.values
local nodes = {   -- modelled positions (x left, y rear, z up)
  fl1l = vec3(0.215, -0.674, 0.075), fl1r = vec3(-0.215, -0.674, 0.075),
  fl3l = vec3(0.4, 0.597, 0.100), fl3r = vec3(-0.4, 0.597, 0.100),
  fl2 = vec3(0, 0.057, 0.084), fl4 = vec3(0, 1.378, 0.122),
  fw1l = vec3(0.657, -1.525, 0.338), fw1r = vec3(-0.657, -1.525, 0.338),
  rw1l = vec3(0.654, 2.03, 0.335), rw1r = vec3(-0.654, 2.03, 0.335),
}
local names, cids = {}, {}
local i = 0
for n, _ in pairs(nodes) do names[i] = n; cids[n] = i; i = i + 1 end
local drop = 0      -- chassis lowered by this much (wheels stay put)
v = {data = {nodes = {}}}
for c, n in pairs(names) do v.data.nodes[c] = {name = n, cid = c} end
obj = {getNodePosition = function(self, cid)
  local n = names[cid]
  local p = nodes[n]
  if n:sub(1, 2) == "fw" or n:sub(1, 2) == "rw" then return p end
  return p - vec3(0, 0, drop)
end}
local ge = require("redbullGroundEffect")
ge.init({floorClA = 2.0, gain = 12, stallHeight = 0.018, stallLoss = 0.8, maxForce = 8000, radius = 0.335, h0F = 0.0719, h0R = 0.1221})
e.airspeed = 83.3
run(ge, 1, 0.02)
check(math.abs(e.floorGE - 1) < 0.01 and e.floorGEDown < 0.01 and e.floorGEUp < 0.01, "no extra force at the modelled ride height")
drop = 0.025
run(ge, 1, 0.02)
check(e.floorGE > 1.25 and e.floorGEDown > 0.3, string.format("25 mm lower: g %.2f, down control %.2f", e.floorGE, e.floorGEDown))
local g25 = e.floorGE
drop = 0.062
run(ge, 1, 0.02)
check(e.floorGE < g25 and e.rideHeightF < 0.018, string.format("near the ground the floor stalls: g %.2f at %.0f mm (%.2f at 25 mm lower)", e.floorGE, e.rideHeightF * 1000, g25))
drop = -0.03
run(ge, 1, 0.02)
check(e.floorGE < 1 and e.floorGEUp > 0, string.format("30 mm higher: g %.2f, up control %.2f", e.floorGE, e.floorGEUp))

-- ------------------------------------------------------------ traction
print("redbullTraction")
electrics.values = {}
e = electrics.values
local rr, rl = {name = "RR", wheelSpeed = 0}, {name = "RL", wheelSpeed = 0}
wheels = {wheels = {rr, rl, {name = "FR", wheelSpeed = 0}}}
local tc = require("redbullTraction")
tc.init({targetSlip = 0.12, minSlipSpeed = 2.5, gain = 4.0, release = 3.0})
e.airspeed = 10
rr.wheelSpeed, rl.wheelSpeed = 10.5, 10.5
e.throttle = 1
tc.updateGFX(0.02)
check(e.throttle == 1 and e.tcActive == 0, "gripping: throttle untouched")
for _ = 1, 10 do rr.wheelSpeed, rl.wheelSpeed = 20, 20; e.throttle = 1; tc.updateGFX(0.02) end
check(e.throttle < 0.9 and e.tcActive == 1, string.format("rears spinning at 2x road speed: throttle trimmed to %.2f", e.throttle))
for _ = 1, 50 do rr.wheelSpeed, rl.wheelSpeed = 10.5, 10.5; e.throttle = 1; tc.updateGFX(0.02) end
check(e.throttle == 1, "grip back: full throttle restored")
e.tcMode = 0
for _ = 1, 5 do rr.wheelSpeed, rl.wheelSpeed = 20, 20; e.throttle = 1; tc.updateGFX(0.02) end
check(e.throttle == 1, "switched off: no trimming")

-- ------------------------------------------------------------ steering check
print("redbullSteerCheck")
electrics.values = {}
e = electrics.values
local sn = {   -- x left, y rear, z up
  fx1r = vec3(-0.23, -1.59, 0.26), fx1l = vec3(0.23, -1.59, 0.26), fx2r = vec3(-0.26, -1.05, 0.26), fx2l = vec3(0.26, -1.05, 0.26),
  fw1l = vec3(0.33, -1.85, 0.34), fw1ll = vec3(0.60, -1.85, 0.34), fw1r = vec3(-0.33, -1.85, 0.34), fw1rr = vec3(-0.60, -1.85, 0.34),
}
local snames = {}
local si = 0
v = {data = {nodes = {}}}
for n, _ in pairs(sn) do v.data.nodes[si] = {name = n, cid = si}; snames[si] = n; si = si + 1 end
obj = {getNodePosition = function(self, c) return sn[snames[c]] end}
local sc = require("redbullSteerCheck")
sc.init({})
sc.updateGFX(0.02)
check(math.abs(e.steerAngleFL) < 1e-6 and math.abs(e.steerAngleFR) < 1e-6, "straight wheels read 0 deg")
-- steer both wheels 5 deg left (forward is -y, left +x): the axles' outer ends swing rearward
local d = math.rad(-5)
local function rot(c, p) local r = p - c; return c + vec3(r.x * math.cos(d) + r.y * math.sin(d), -r.x * math.sin(d) + r.y * math.cos(d), r.z) end
sn.fw1ll = rot(sn.fw1l, sn.fw1ll)
sn.fw1rr = rot(sn.fw1r, sn.fw1rr)
e.steerCheck = 1
sc.updateGFX(0.02)
check(math.abs(e.steerAngleFL - 5) < 0.01 and math.abs(e.steerAngleFR - 5) < 0.01,
      string.format("5 deg left lock reads L %+.2f R %+.2f", e.steerAngleFL, e.steerAngleFR))

print(failures == 0 and "all controller checks passed" or (failures .. " check(s) FAILED"))
os.exit(failures == 0 and 0 or 1)
