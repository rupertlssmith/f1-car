-- Steering alignment readout for the redbull mod (diagnostic).
--
-- Action "steerCheck" (key J) toggles an on-screen line, updated twice a
-- second: the steering input and the two front wheels' measured steer
-- angles (from the wheel axle nodes, in the chassis frame; + = left).
-- Driving straight with a centred input, both angles should read ~0 (plus
-- the static toe). If they don't, the steering itself is off-centre; if
-- they do but you still need an angle to go straight, the car is pulling.
-- A second line tracks what could make the car pull with the steering
-- centred: rear wheel angles (toe), chassis roll against the plane of the
-- wheel centres, each front-wing tip's height change since spawn (a bent
-- wing), and the left-right wheel-speed difference (tyre radius).
-- Electrics out: steerCheck, steerAngleFL / FR / RL / RR (deg), chassisRoll
-- (deg), wingTipL / wingTipR (mm), rearSpeedDiff (%).

local M = {}
M.type = "auxiliary"

local cid = {}
local enabled = true
local timer = 0
local lastMode = 0

local function pos(n) return obj:getNodePosition(cid[n]) end

-- steer angle of one wheel (deg, + = left) from its axle nodes
local function angle(inner, outer, sign, fwd, left)
  local a = (pos(outer) - pos(inner)) * sign     -- points to the car's left
  return math.deg(math.atan2(-a:dot(fwd), a:dot(left)))
end

local tip0                -- front-wing tip heights at spawn (chassis frame)
local wheelData = {}

local function frame()
  local front = (pos("fx1r") + pos("fx1l")) * 0.5
  local back = (pos("fx2r") + pos("fx2l")) * 0.5      -- level with fx1: a flat forward axis
  local fwd = (front - back):normalized()
  local left = pos("fx1l") - pos("fx1r")
  left = (left - fwd * left:dot(fwd)):normalized()
  return fwd, left, fwd:cross(left)
end

local function measure()
  local fwd, left = frame()
  return angle("fw1l", "fw1ll", 1, fwd, left), angle("fw1r", "fw1rr", -1, fwd, left)
end

local function measureMore()
  local fwd, left, up = frame()
  local rl, rr = angle("rw1l", "rw1ll", 1, fwd, left), angle("rw1r", "rw1rr", -1, fwd, left)
  -- roll: chassis left axis against the plane of the wheel centres
  local wl = (pos("fw1ll") + pos("rw1ll")) * 0.5
  local wr = (pos("fw1rr") + pos("rw1rr")) * 0.5
  local wf = (pos("fw1ll") + pos("fw1rr")) * 0.5
  local wb = (pos("rw1ll") + pos("rw1rr")) * 0.5
  local wup = (wl - wr):cross(wf - wb):normalized()
  local roll = math.deg(math.asin(math.max(-1, math.min(1, left:dot(wup)))))
  local tl = (pos("fep1l") - pos("fx1l")):dot(up)
  local tr = (pos("fep1r") - pos("fx1r")):dot(up)
  if not tip0 then tip0 = {tl, tr} end
  local sl, sr, n = 0, 0, 0
  for _, wd in pairs(wheelData) do
    local ok, s = pcall(function() return wd.wheelSpeed end)
    if ok and s and wd.name == "RL" then sl = s; n = n + 1 end
    if ok and s and wd.name == "RR" then sr = s; n = n + 1 end
  end
  local diff = (n == 2 and (sl + sr) > 2) and (sl - sr) / ((sl + sr) / 2) * 100 or 0
  return rl, rr, roll, (tl - tip0[1]) * 1000, (tr - tip0[2]) * 1000, diff
end

local function updateGFX(dt)
  local mode = electrics.values.steerCheck or 0
  if not enabled then return end
  if mode ~= lastMode then
    lastMode = mode
    if mode == 0 then guihooks.message({txt = "Steering check: off", context = {}}, 2, "redbullSteerCheck", "settings") end
    timer = 0
  end
  local ok, l, r = pcall(measure)
  if not ok then
    enabled = false
    log("E", "redbullSteerCheck", "disabled: " .. tostring(l))
    return
  end
  electrics.values.steerAngleFL, electrics.values.steerAngleFR = l, r
  local ok2, rl, rr, roll, tipL, tipR, diff = pcall(measureMore)
  if ok2 then
    electrics.values.steerAngleRL, electrics.values.steerAngleRR = rl, rr
    electrics.values.chassisRoll, electrics.values.rearSpeedDiff = roll, diff
    electrics.values.wingTipL, electrics.values.wingTipR = tipL, tipR
  end
  if mode == 0 then return end
  timer = timer - dt
  if timer <= 0 then
    timer = 0.5
    local input = electrics.values.steering_input or 0
    guihooks.message({txt = string.format("Steer input %+.3f | front wheels L %+.2f° R %+.2f° (mean %+.2f°)",
      input, l, r, (l + r) / 2), context = {}}, 1, "redbullSteerCheck", "settings")
    if ok2 then
      guihooks.message({txt = string.format("Rear wheels L %+.2f° R %+.2f° | roll %+.2f° | wing tips L %+.0f R %+.0f mm | rear speed L-R %+.2f%%",
        rl, rr, roll, tipL, tipR, diff), context = {}}, 1, "redbullSteerCheck2", "settings")
    end
  end
end

local function reset()
  timer = 0
  tip0 = nil
end

local function init(jbeamData)
  cid = {}
  for _, n in pairs(v.data.nodes) do
    if n.name then cid[n.name] = n.cid end
  end
  for _, n in ipairs({"fx1r", "fx1l", "fx2r", "fx2l", "fw1l", "fw1ll", "fw1r", "fw1rr", "rw1l", "rw1ll", "rw1r", "rw1rr", "fep1l", "fep1r"}) do
    if not cid[n] then
      enabled = false
      log("E", "redbullSteerCheck", "node " .. n .. " missing; steering check disabled")
    end
  end
  wheelData = (wheels and wheels.wheels) or {}
  electrics.values.steerCheck = 0
  reset()
end

M.init = init
M.reset = reset
M.updateGFX = updateGFX

return M
