-- RB14 ride-height sensitive floor (experimental) for the redbull mod.
--
-- BeamNG's aero triangles give the floor a fixed lift coefficient that only
-- follows its angle of attack (rake). A real 2018 floor also gains downforce
-- as it gets closer to the ground and stalls when it gets too close. This
-- controller measures the front and rear ride height from node positions
-- (floor above the plane of the wheel centres) and adds the
-- difference between that ground-effect model and the static floor as
-- thruster forces (thrusters in redbull_floor.jbeam, part
-- redbull_floor_groundeffect):
--
--   g(h) = 1 + gain * (h0 - h)                       closer to the ground: more
--   g   *= stall factor when the front of the floor is below stallHeight
--   extra force = (g - 1) * 0.5 * rho * v^2 * floorClA
--
-- electrics out: floorGEDown / floorGEUp (0..1 thruster controls, split
-- front/rear), floorGE (g), rideHeightF / rideHeightR (m).

local M = {}
M.type = "auxiliary"

local floorClA = 2.0          -- m^2, the static floor's share of ClA
local gain = 12               -- 1/m: +1.2 % downforce per mm lower
local stallHeight = 0.018     -- m, front floor height where it starts to stall
local stallLoss = 0.8         -- share of floor downforce lost when fully stalled
local maxForce = 8000         -- N, thruster factor (per direction, all thrusters)
local rearShare = 0.64        -- share of the force on the rear thrusters
local radius = 0.335
local rho = 1.225

local names = {}
local cid = {}
local h0F, h0R
local enabled = true
local smoothF, smoothR = 0, 0

local function pos(name)
  return obj:getNodePosition(cid[name])
end

local function mid(a, b)
  return (pos(a) + pos(b)) * 0.5
end

-- ride height = floor above the plane of the four wheel centres (parallel to
-- the road with the wheels on it), plus the tyre radius
local function measure()
  local wheelF = mid(names.wheelFL, names.wheelFR)
  local wheelR = mid(names.wheelRL, names.wheelRR)
  local left = mid(names.wheelFL, names.wheelRL) - mid(names.wheelFR, names.wheelRR)
  local up = left:cross(wheelR - wheelF):normalized()
  local hF = (mid("fl1l", "fl1r") - wheelF):dot(up) + radius
  local hR = (pos("fl4") - wheelR):dot(up) + radius
  return hF, hR
end

local function updateGFX(dt)
  if not enabled then return end
  local ok, hF, hR = pcall(measure)
  if not ok then
    enabled = false
    log("E", "redbullGroundEffect", "disabled: " .. tostring(hF))
    electrics.values.floorGEDown, electrics.values.floorGEUp = 0, 0
    return
  end
  if not h0F then h0F, h0R, smoothF, smoothR = hF, hR, hF, hR end
  -- light smoothing: the thrusters shouldn't feed wheel hop back into the floor
  local a = math.min(1, dt * 20)
  smoothF = smoothF + (hF - smoothF) * a
  smoothR = smoothR + (hR - smoothR) * a

  local dh = 0.4 * (h0F - smoothF) + 0.6 * (h0R - smoothR)   -- + = lower than static
  local g = 1 + gain * dh
  if smoothF < stallHeight then
    -- the diffuser chokes: the loss builds over the last half of stallHeight
    g = g * (1 - stallLoss * math.min(1, (stallHeight - smoothF) / (0.5 * stallHeight)))
  end
  g = math.max(0.3, math.min(1.6, g))

  local v = electrics.values.airspeed or electrics.values.wheelspeed or 0
  local extra = (g - 1) * 0.5 * rho * v * v * floorClA
  local control = math.min(1, math.abs(extra) / maxForce)
  electrics.values.floorGEDown = extra > 0 and control or 0
  electrics.values.floorGEUp = extra < 0 and control or 0
  electrics.values.floorGE = g
  electrics.values.rideHeightF = smoothF
  electrics.values.rideHeightR = smoothR
end

local refF, refR          -- reference ride heights given by the jbeam, if any

local function reset()
  h0F, h0R = refF, refR
  smoothF, smoothR = h0F or 0, h0R or 0
  electrics.values.floorGEDown, electrics.values.floorGEUp = 0, 0
end

local function init(jbeamData)
  floorClA = jbeamData.floorClA or floorClA
  gain = jbeamData.gain or gain
  stallHeight = jbeamData.stallHeight or stallHeight
  stallLoss = jbeamData.stallLoss or stallLoss
  maxForce = jbeamData.maxForce or maxForce
  radius = jbeamData.radius or radius
  refF, refR = jbeamData.h0F, jbeamData.h0R   -- modelled ride heights (nil: measure at start)
  names = {wheelFL = "fw1l", wheelFR = "fw1r", wheelRL = "rw1l", wheelRR = "rw1r"}
  local want = {"fl1l", "fl1r", "fl4", "fw1l", "fw1r", "rw1l", "rw1r"}
  cid = {}
  for _, n in pairs(v.data.nodes) do
    if n.name then cid[n.name] = n.cid end
  end
  for _, n in ipairs(want) do
    if not cid[n] then
      enabled = false
      log("E", "redbullGroundEffect", "node " .. n .. " missing; ground effect disabled")
    end
  end
  reset()
end

M.init = init
M.reset = reset
M.updateGFX = updateGFX

return M
