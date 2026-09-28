-- Steering alignment readout for the redbull mod (diagnostic).
--
-- Action "steerCheck" (key J) toggles an on-screen line, updated twice a
-- second: the steering input and the two front wheels' measured steer
-- angles (from the wheel axle nodes, in the chassis frame; + = left).
-- Driving straight with a centred input, both angles should read ~0 (plus
-- the static toe). If they don't, the steering itself is off-centre; if
-- they do but you still need an angle to go straight, the car is pulling.
-- Electrics out: steerCheck, steerAngleFL / steerAngleFR (deg).

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

local function measure()
  local front = (pos("fx1r") + pos("fx1l")) * 0.5
  local back = (pos("fx2r") + pos("fx2l")) * 0.5      -- level with fx1: a flat forward axis
  local fwd = (front - back):normalized()
  local left = pos("fx1l") - pos("fx1r")
  left = (left - fwd * left:dot(fwd)):normalized()
  return angle("fw1l", "fw1ll", 1, fwd, left), angle("fw1r", "fw1rr", -1, fwd, left)
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
  if mode == 0 then return end
  timer = timer - dt
  if timer <= 0 then
    timer = 0.5
    local input = electrics.values.steering_input or 0
    guihooks.message({txt = string.format("Steer input %+.3f | front wheels L %+.2f° R %+.2f° (mean %+.2f°)",
      input, l, r, (l + r) / 2), context = {}}, 1, "redbullSteerCheck", "settings")
  end
end

local function reset()
  timer = 0
end

local function init(jbeamData)
  cid = {}
  for _, n in pairs(v.data.nodes) do
    if n.name then cid[n.name] = n.cid end
  end
  for _, n in ipairs({"fx1r", "fx1l", "fx2r", "fx2l", "fw1l", "fw1ll", "fw1r", "fw1rr"}) do
    if not cid[n] then
      enabled = false
      log("E", "redbullSteerCheck", "node " .. n .. " missing; steering check disabled")
    end
  end
  electrics.values.steerCheck = 0
  reset()
end

M.init = init
M.reset = reset
M.updateGFX = updateGFX

return M
