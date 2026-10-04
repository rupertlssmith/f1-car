-- Virtual sensors for the redbull mod (round 17, always on).
--
-- Measures the geometry that could make the car keep turning after a hard
-- corner (the inner rear wheel loses ~3 deg of toe-in and holds it for ~2 s,
-- see plans/rb14-model-swap.md) and publishes it as electrics values, so
-- every BeamNG replay records it (tools/rb14/replay_analysis.py reads them).
-- Nothing is shown on screen. All values come from node positions.
--
-- Frames: "tub" -- front bulkhead (fx1 / fx2), as the steering check;
-- "gearbox" -- the rear structure the rear suspension hangs from (rx1 front,
-- rx2 rear, origin at the differential node rdiff). x = left, y = forward,
-- z = up; angles + = pointing left.
--
-- Per rear wheel S = L / R (electrics sn_RL_* / sn_RR_*):
--   toe, camber        axle line against the gearbox frame (deg)
--   in_x/y/z, out_x/y/z   inner / outer axle node in the gearbox frame (mm)
--   shaft              driveshaft length, axle node to rdiff (mm; its end
--                      stops engage at +-5 % x $halfshaft_play)
--   spring             upright to rocker (rh1 - rs1) length (mm): wheel travel
--   hub_<in|out>_<rh1|rh3|rh4>   axle node to upright node distances (mm):
--                      is the hub shifting on its upright?
--   link_<rxN>_<rhN>   the six upright-to-gearbox link lengths (mm)
-- Front: sn_FL_wobble / sn_FR_wobble (deg RMS of the front wheel's angle
-- above ~3 Hz, over 0.5 s, at frame rate).
-- Plus: sn_rearYaw (deg, gearbox frame vs tub frame: the rear structure
-- turning on the tub), sn_FL_toe / sn_FR_toe (tub frame), sn_rack (rack
-- node to rail end, mm), sn_FL_tierod / sn_FR_tierod (mm), and the wheel
-- loads sn_load_<wheel> (N) where the game provides them.

local M = {}
M.type = "auxiliary"

local cid = {}
local ok = {}
local wheelData = {}

local function has(what, ...)
  for _, n in ipairs({...}) do
    if not cid[n] then
      log("E", "redbullSensors", what .. " sensors off: node " .. n .. " missing")
      return false
    end
  end
  return true
end

local function pos(n) return obj:getNodePosition(cid[n]) end
local function dist(a, b) return (pos(a) - pos(b)):length() * 1000 end

local function frame(f1r, f1l, f2r, f2l)
  local front = (pos(f1r) + pos(f1l)) * 0.5
  local back = (pos(f2r) + pos(f2l)) * 0.5
  local fwd = (front - back):normalized()
  local left = pos(f1l) - pos(f1r)
  left = (left - fwd * left:dot(fwd)):normalized()
  return fwd, left, fwd:cross(left)
end

-- wheel heading (deg, + = left) and camber (deg, + = top out) from axle nodes
local function angles(inner, outer, sign, fwd, left, up)
  local a = (pos(outer) - pos(inner)) * sign      -- points to the car's left
  local toe = math.deg(math.atan2(-a:dot(fwd), a:dot(left)))
  local camber = math.deg(math.atan2(a:dot(up), a:dot(left))) * sign
  return toe, camber
end

local REAR_LINKS = {{"rx2", "rh1"}, {"rx1", "rh1"}, {"rx4", "rh3"}, {"rx3", "rh4"}, {"rx3", "rh3"}, {"rx4", "rh4"}}

-- front-wheel wobble (round 20): each front wheel's angle high-passed at
-- ~3 Hz (minus its 50 ms-smoothed trend) and RMS-averaged over 0.5 s, at the
-- game's frame rate (finer than a replay's ~30 frames/s, so a fast shimmy
-- shows here even when a replay would alias it)
local wob = {FL = {lp = nil, ms = 0}, FR = {lp = nil, ms = 0}}
local WOB_TAU, WOB_AVG = 0.05, 0.5

local function wobble(S, toe, dt)
  local w = wob[S]
  if not w.lp then w.lp = toe end
  w.lp = w.lp + (toe - w.lp) * math.min(1, dt / WOB_TAU)
  local r = toe - w.lp
  w.ms = w.ms + (r * r - w.ms) * math.min(1, dt / WOB_AVG)
  return math.sqrt(w.ms)
end

local function measure(dt)
  local ev = electrics.values
  local tf, tl, tu = frame("fx1r", "fx1l", "fx2r", "fx2l")
  local gf, gl, gu = frame("rx1r", "rx1l", "rx2r", "rx2l")
  local o = pos("rdiff")
  ev.sn_rearYaw = math.deg(math.atan2(-gf:dot(tl), gf:dot(tf)))
  for _, S in ipairs({"L", "R"}) do
    local s = S:lower()
    local inner, outer, sign = "rw1" .. s, "rw1" .. s .. s, (S == "L") and 1 or -1
    if ok["R" .. S] then
      local toe, camber = angles(inner, outer, sign, gf, gl, gu)
      local p = "sn_R" .. S .. "_"
      ev[p .. "toe"], ev[p .. "camber"] = toe, camber
      for _, end_ in ipairs({{"in", inner}, {"out", outer}}) do
        local d = pos(end_[2]) - o
        ev[p .. end_[1] .. "_x"] = d:dot(gl) * 1000
        ev[p .. end_[1] .. "_y"] = d:dot(gf) * 1000
        ev[p .. end_[1] .. "_z"] = d:dot(gu) * 1000
        for _, u in ipairs({"rh1", "rh3", "rh4"}) do
          ev[p .. "hub_" .. end_[1] .. "_" .. u] = dist(end_[2], u .. s)
        end
      end
      ev[p .. "shaft"] = dist(inner, "rdiff")
      ev[p .. "spring"] = dist("rh1" .. s, "rs1")
      for _, l in ipairs(REAR_LINKS) do
        ev[p .. "link_" .. l[1] .. "_" .. l[2]] = dist(l[1] .. s, l[2] .. s)
      end
    end
    if ok["F" .. S] then
      local toe = angles("fw1" .. s, "fw1" .. s .. s, sign, tf, tl, tu)
      ev["sn_F" .. S .. "_toe"] = toe
      if dt and dt > 0 then ev["sn_F" .. S .. "_wobble"] = wobble("F" .. S, toe, dt) end
      ev["sn_F" .. S .. "_tierod"] = dist("fh3" .. s, "fh6" .. s)
    end
  end
  if ok.rack then ev.sn_rack = dist("fh6r", "fx3r") end
  for _, wd in pairs(wheelData) do
    local okv, f = pcall(function() return wd.downForceRaw or wd.downForce end)
    if okv and type(f) == "number" and wd.name then ev["sn_load_" .. wd.name] = f end
  end
end

local enabled = true

local function updateGFX(dt)
  if not enabled then return end
  local fine, err = pcall(measure, dt)
  if not fine then
    enabled = false
    log("E", "redbullSensors", "disabled: " .. tostring(err))
  end
end

local function reset()
  wob = {FL = {lp = nil, ms = 0}, FR = {lp = nil, ms = 0}}
end

local function init(jbeamData)
  cid = {}
  for _, n in pairs(v.data.nodes) do
    if n.name then cid[n.name] = n.cid end
  end
  local frames = has("all", "fx1r", "fx1l", "fx2r", "fx2l", "rx1r", "rx1l", "rx2r", "rx2l", "rdiff")
  for _, S in ipairs({"L", "R"}) do
    local s = S:lower()
    ok["R" .. S] = frames and has("R" .. S, "rw1" .. s, "rw1" .. s .. s, "rh1" .. s, "rh3" .. s, "rh4" .. s, "rs1",
                                  "rx1" .. s, "rx2" .. s, "rx3" .. s, "rx4" .. s)
    ok["F" .. S] = frames and has("F" .. S, "fw1" .. s, "fw1" .. s .. s, "fh3" .. s, "fh6" .. s)
  end
  ok.rack = has("rack", "fh6r", "fx3r")
  enabled = frames
  wheelData = (wheels and wheels.wheels) or {}
end

M.init = init
M.reset = reset
M.updateGFX = updateGFX

return M
