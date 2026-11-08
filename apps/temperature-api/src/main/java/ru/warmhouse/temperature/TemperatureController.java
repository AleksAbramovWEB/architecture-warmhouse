package ru.warmhouse.temperature;

import java.util.Map;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class TemperatureController {

    private final TemperatureService temperatureService;

    public TemperatureController(TemperatureService temperatureService) {
        this.temperatureService = temperatureService;
    }

    @GetMapping({"/temperature", "/temperature/{sensorId}"})
    public ResponseEntity<TemperatureResponse> temperature(
            @PathVariable(name = "sensorId", required = false) String pathSensorId,
            @RequestParam(name = "sensorId", required = false) String querySensorId,
            @RequestParam(name = "sensor_id", required = false) String legacySensorId,
            @RequestParam(name = "location", required = false) String location) {
        String sensorId = firstNonEmpty(pathSensorId, querySensorId, legacySensorId);
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .body(temperatureService.read(sensorId, location));
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok");
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) {
            if (value != null && !value.isEmpty()) {
                return value;
            }
        }
        return null;
    }
}
