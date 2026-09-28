-- RB14 torque map / traction limiter for the redbull mod.
--
-- 2018 F1 cars had no traction control, but their engine torque maps cut
-- torque in the low gears so ~900 hp didn't just light up the rears. This
-- controller does that job from the wheels: it compares the driven (rear)
-- wheels' speed with the car's speed and trims the throttle when the rears
-- slip more than targetSlip, releasing it again as grip returns.
--
-- Action "tcMode" toggles it (on by default). Electrics out: tcActive (0/1
-- while trimming), tcMode.

local M = {}
M.type = "auxiliary"
M.defaultOrder = 1100     -- after vehicleController and the ERS cap

local targetSlip = 0.12    -- slip ratio the rears may run
local minSlipSpeed = 2.5   -- m/s of rear wheel overspeed always allowed
local gain = 4.0           -- throttle cut per unit of excess slip
local release = 3.0        -- how fast the cut recovers (1/s)
local cut = 0
local lastMode = -1
local rearWheels = {}

local function rearSpeed()
  local sum, n = 0, 0
  for _, wd in pairs(rearWheels) do
    local ok, s = pcall(function() return math.abs(wd.wheelSpeed or 0) end)
    if ok then sum, n = sum + s, n + 1 end
  end
  if n == 0 then return nil end
  return sum / n
end

local function updateGFX(dt)
  local mode = electrics.values.tcMode or 1
  if mode ~= lastMode then
    lastMode = mode
    guihooks.message({txt = mode == 1 and "Torque map: on" or "Torque map: off", context = {}}, 2, "redbullTraction", "settings")
  end
  if mode == 0 then
    cut = 0
    electrics.values.tcActive = 0
    return
  end
  local car = electrics.values.airspeed or electrics.values.wheelspeed or 0
  local rear = rearSpeed() or electrics.values.wheelspeed or car
  local allowed = math.max(car * (1 + targetSlip), car + minSlipSpeed)
  local excess = (rear - allowed) / math.max(car, 5)
  if excess > 0 and (electrics.values.throttle or 0) > 0.05 then
    cut = math.min(0.85, cut + gain * excess * dt * 10)
  else
    cut = math.max(0, cut - release * dt)
  end
  if cut > 0 then
    electrics.values.throttle = (electrics.values.throttle or 0) * (1 - cut)
  end
  electrics.values.tcActive = cut > 0.02 and 1 or 0
end

local function reset()
  cut = 0
  lastMode = -1
  electrics.values.tcActive = 0
end

local function init(jbeamData)
  targetSlip = jbeamData.targetSlip or targetSlip
  minSlipSpeed = jbeamData.minSlipSpeed or minSlipSpeed
  gain = jbeamData.gain or gain
  release = jbeamData.release or release
  rearWheels = {}
  for _, wd in pairs(wheels.wheels) do
    if wd.name and wd.name:sub(1, 1) == "R" then table.insert(rearWheels, wd) end
  end
  electrics.values.tcMode = 1
  reset()
end

M.init = init
M.reset = reset
M.updateGFX = updateGFX

return M
