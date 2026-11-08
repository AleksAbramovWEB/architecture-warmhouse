package ru.warmhouse.temperature;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
import org.springframework.stereotype.Service;

@Service
public class TemperatureService {

    private static final int MIN_CENTS = 1500;
    private static final int VALUE_COUNT = 1501;
    private static final Map<String, String> LOCATIONS = Map.of(
            "1", "Living Room", "2", "Bedroom", "3", "Kitchen");

    private final ConcurrentHashMap<SensorKey, Integer> previousValues = new ConcurrentHashMap<>();

    public TemperatureResponse read(String sensorId, String location) {
        if (location == null || location.isEmpty()) {
            location = sensorId == null ? "Unknown" : LOCATIONS.getOrDefault(sensorId, "Unknown");
        }
        if (sensorId == null || sensorId.isEmpty()) {
            String requestedLocation = location;
            sensorId = LOCATIONS.entrySet().stream()
                    .filter(entry -> entry.getValue().equals(requestedLocation))
                    .map(Map.Entry::getKey)
                    .findFirst()
                    .orElse("0");
        }

        // compute atomically chooses a new sample for this sensor, excluding its previous value.
        int index = previousValues.compute(new SensorKey(sensorId, location), (key, previous) -> {
            int next = ThreadLocalRandom.current().nextInt(previous == null ? VALUE_COUNT : VALUE_COUNT - 1);
            return previous != null && next >= previous ? next + 1 : next;
        });

        return new TemperatureResponse(
                BigDecimal.valueOf(MIN_CENTS + index, 2), "°C", Instant.now(), location,
                "active", sensorId, "temperature", "Simulated temperature sensor");
    }

    private record SensorKey(String sensorId, String location) {
    }
}
