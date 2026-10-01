-- Runs the mod's Lua controllers on one car's real nodes and parameters,
-- with the game stubbed (as in test_controllers.lua), and prints what the
-- game would show as console errors. Called by tools/check_mod.py:
--
--     luajit tools/rb14/check_controllers.lua <car.lua>
--
-- <car.lua> returns {nodes = {name = {x, y, z}}, controllers = {{name,
-- path, params}}}. Output lines: "ERROR <controller>: ..." / "WARN ...".
-- A node the controller asks for that the car lacks is an ERROR; so is a
-- Lua error in init / updateGFX and any log("E") (a controller disabling
-- itself); log("W") is a WARN.

local car = dofile(arg[1])
local current = "?"
local function report(level, msg) print(level .. " " .. current .. ": " .. msg) end

electrics = {values = {}}
guihooks = {message = function() end, trigger = function() end}
function log(level, _, msg)
  if level == "E" then report("ERROR", msg) elseif level == "W" then report("WARN", msg) end
end
local V = {}
V.__index = V
function vec3(x, y, z) return setmetatable({x = x or 0, y = y or 0, z = z or 0}, V) end
V.__add = function(a, b) return vec3(a.x + b.x, a.y + b.y, a.z + b.z) end
V.__sub = function(a, b) return vec3(a.x - b.x, a.y - b.y, a.z - b.z) end
V.__mul = function(a, s) return vec3(a.x * s, a.y * s, a.z * s) end
V.__unm = function(a) return vec3(-a.x, -a.y, -a.z) end
function V:dot(b) return self.x * b.x + self.y * b.y + self.z * b.z end
function V:cross(b) return vec3(self.y * b.z - self.z * b.y, self.z * b.x - self.x * b.z, self.x * b.y - self.y * b.x) end
function V:length() return math.sqrt(self:dot(self)) end
function V:normalized() local l = self:length(); return l > 0 and self * (1 / l) or vec3(0, 0, 0) end

-- node table as the game gives it (v.data.nodes, keyed by cid)
local byCid, i = {}, 0
v = {data = {nodes = {}, wheels = {}}}
for n, p in pairs(car.nodes) do
  v.data.nodes[i] = {name = n, cid = i, pos = vec3(p[1], p[2], p[3])}
  byCid[i] = n
  i = i + 1
end
obj = {}
function obj:getNodePosition(c)
  if c == nil or byCid[c] == nil then error("asked for a node the car does not have", 2) end
  local p = car.nodes[byCid[c]]
  return vec3(p[1], p[2], p[3])
end
function obj:getVelocity() return vec3(0, -30, 0) end
function obj:getDirectionVector() return vec3(0, -1, 0) end
function obj:getDirectionVectorUp() return vec3(0, 0, 1) end
function obj:getGroundSpeed() return 30 end
function obj:getAirflowSpeed() return 30 end
function obj:getId() return 1 end
wheels = {wheels = {}}
powertrain = {getDevice = function() return nil end, getDevicesByCategory = function() return {} end}
input = {event = function() end}
sensors = {gx = 0, gy = 0, gz = -9.81}

local e = electrics.values
local function drive()
  e.throttle, e.brake, e.steering, e.rpm, e.wheelspeed, e.airspeed, e.gear = 0.5, 0, 0, 9000, 30, 30, 4
  e.ignitionLevel, e.running = 2, true
end

for _, c in ipairs(car.controllers) do
  current = c.name
  local chunk, err = loadfile(c.path)
  if not chunk then report("ERROR", "does not load: " .. tostring(err))
  else
    local ok, M = pcall(chunk)
    if not ok then report("ERROR", "does not load: " .. tostring(M))
    elseif type(M) == "table" then
      drive()
      local fine, msg = true, nil
      if M.init then fine, msg = pcall(M.init, c.params or {}) end
      if not fine then report("ERROR", "init: " .. tostring(msg))
      else
        for _ = 1, 5 do
          drive()
          for _, fn in ipairs({"updateGFX", "update"}) do
            if M[fn] and fine then
              fine, msg = pcall(M[fn], 0.02)
              if not fine then report("ERROR", fn .. ": " .. tostring(msg)) end
            end
          end
        end
      end
    end
  end
end
