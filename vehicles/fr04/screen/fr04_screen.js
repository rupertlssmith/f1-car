angular.module('gaugesScreen', [])
.controller('GaugesScreenController', function($scope, $window) {
  var units = {uiUnitConsumptionRate: "metric",
  uiUnitDate: "ger",
  uiUnitEnergy: "metric",
  uiUnitLength: "metric",
  uiUnitPower: "hp",
  uiUnitPressure: "bar",
  uiUnitTemperature: "c",
  uiUnitTorque: "metric",
  uiUnitVolume: "l",
  uiUnitWeight: "kg"};


  $scope.data = {}
  // overwriting plain javascript function so we can access from within the controller
    $window.setup = (data) => {
	if (units.uiUnitLength === "metric") {
		$scope.data.speedUnit = "km/h";
	}
	else {
		$scope.data.speedUnit = "mph";
	}
  }
	$window.updateData = (data) => {
			$scope.$evalAsync(function() {

			//gear selector
			if (data.electrics.gear === -1) {
				$scope.data.gear = "R";
			}
			else if (data.electrics.gear === 0) {
				$scope.data.gear = "N";
			}
			else {
				$scope.data.gear = data.electrics.gear;
			}

			$scope.data.TopCenterVal = ((data.electrics.rpmTacho).toFixed(0));

			// checking gauge cluster units
			if (units.uiUnitLength === "metric") {
				$scope.data.TopRightVal = (data.electrics.wheelspeed * 3.6).toFixed(0);
				$scope.data.TopRightText = "KM/H";
			}
			else {
				$scope.data.TopRightVal = (data.electrics.wheelspeed * 2.23694).toFixed(0);
				$scope.data.TopRightText = "MPH";
			}
			
			if (units.uiUnitTemperature === "c") {
				$scope.data.BottomRightVal = data.electrics.watertemp.toFixed(0);
				$scope.data.BottomRightText = "WAT T";
				$scope.data.BottomLeftVal = data.electrics.oiltemp.toFixed(0);
				$scope.data.BottomLeftText = "OIL T";
				$scope.data.BottomUnit = " C";
			}
			else {
				$scope.data.BottomRightVal = (data.electrics.watertemp * 1.8 + 32).toFixed(0);
				$scope.data.BottomRightText = "WAT T";
				$scope.data.BottomLeftVal = (data.electrics.oiltemp * 1.8 + 32).toFixed(0);
				$scope.data.BottomLeftText = "OIL T";
				$scope.data.BottomUnit = " F";
			}
			
			if (units.uiUnitVolume === "l") {
				$scope.data.TopLeftVal = Math.floor(data.electrics.fuelVolume*10) /10;
				$scope.data.TopLeftText= "FUEL";
				$scope.data.FuelUnit = " L";
			}
			else {
				$scope.data.TopLeftVal = Math.floor(data.electrics.fuelVolume / 3.785 *10) /10;
				$scope.data.TopLeftText= "FUEL";
				$scope.data.FuelUnit = " G";
			}


			var OilTempHigh = false
			var WaterTempHigh = false
			var FuelLevelLow = false
			var PitLimiterEnabled = false
			var BrakeBiasChanged = false

			//setup messages
			if (data.electrics.oiltemp >= 120)      {OilTempHigh = true}       else {OilTempHigh = false}
			if (data.electrics.watertemp >= 120)    {WaterTempHigh = true}     else {WaterTempHigh = false}
			if (data.electrics.fuelVolume <= 5)     {FuelLevelLow = true}      else {FuelLevelLow = false}
			if (data.electrics.pitLimiter == 1)     {PitLimiterEnabled = true} else {PitLimiterEnabled = false}
			if (data.electrics.biasDifferent > 0)  {BrakeBiasChanged = true} else {BrakeBiasChanged = false}

			//setup brake bias timer
			if (BrakeBiasChanged){
				document.getElementById("BiasBox").style.visibility="visible";
			}
			else {
				document.getElementById("BiasBox").style.visibility="hidden";
			}

			$scope.data.BiasMessage = `${data.electrics.biasInfo}`;
			
			//check to show info box
			if (OilTempHigh || WaterTempHigh || FuelLevelLow || PitLimiterEnabled){
				document.getElementById("InfoBox").style.visibility="visible";
			}
			else {
				document.getElementById("InfoBox").style.visibility="hidden";
				$scope.data.InfoMessage = "";
			}

			//info messages
			//from lowest to highest importance
			if (WaterTempHigh){
				$scope.data.InfoMessage = "WATER TEMP HI";
				document.getElementById("WaterTempField").style.backgroundColor="red";
			}
			else {
				document.getElementById("WaterTempField").style.backgroundColor="";
			}
			if (OilTempHigh){
				$scope.data.InfoMessage = "OIL TEMP HI";
				document.getElementById("OilTempField").style.backgroundColor="red";
			}
			else {
				document.getElementById("OilTempField").style.backgroundColor="";
			}
			if (FuelLevelLow){
				$scope.data.InfoMessage = "FUEL LEVEL LOW";
				document.getElementById("FuelLevelField").style.backgroundColor="red";
			}
			else {
				document.getElementById("FuelLevelField").style.backgroundColor="";
			}
			if (PitLimiterEnabled){
				$scope.data.InfoMessage = "PIT LIMITER ON";
			}
			else {}
		})
	}
}
);