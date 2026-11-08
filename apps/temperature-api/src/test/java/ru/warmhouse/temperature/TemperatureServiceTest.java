package ru.warmhouse.temperature;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class TemperatureServiceTest {

    @Test
    void consecutiveReadingsDifferForEachSensorAndStayInRange() {
        TemperatureService service = new TemperatureService();
        Map<String, BigDecimal> previous = new HashMap<>();
        for (int round = 0; round < 1000; round++) {
            for (String id : new String[]{"1", "42"}) {
                BigDecimal value = service.read(id, null).value();
                assertThat(value).isBetween(new BigDecimal("15.00"), new BigDecimal("30.00"));
                assertThat(value.scale()).isEqualTo(2);
                if (previous.containsKey(id)) {
                    assertThat(value).isNotEqualByComparingTo(previous.get(id));
                }
                previous.put(id, value);
            }
        }
    }
}
