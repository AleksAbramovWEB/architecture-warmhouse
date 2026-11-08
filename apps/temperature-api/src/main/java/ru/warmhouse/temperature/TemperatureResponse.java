package ru.warmhouse.temperature;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;
import java.time.Instant;

public record TemperatureResponse(
        BigDecimal value,
        String unit,
        Instant timestamp,
        String location,
        String status,
        @JsonProperty("sensor_id") String sensorId,
        @JsonProperty("sensor_type") String sensorType,
        String description) {
}
