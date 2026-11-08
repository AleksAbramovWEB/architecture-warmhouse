package ru.warmhouse.temperature;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class TemperatureControllerTest {

    @Autowired
    private MockMvc mvc;

    @Autowired
    private ObjectMapper objectMapper;

    @ParameterizedTest
    @CsvSource(delimiter = '|', value = {
            "/temperature?location=Living Room | 1 | Living Room",
            "/temperature?location=Bedroom | 2 | Bedroom",
            "/temperature?location=Kitchen | 3 | Kitchen",
            "/temperature/1 | 1 | Living Room",
            "/temperature/2 | 2 | Bedroom",
            "/temperature/3 | 3 | Kitchen",
            "/temperature/42 | 42 | Unknown",
            "/temperature?sensorId=2 | 2 | Bedroom",
            "/temperature?sensor_id=3 | 3 | Kitchen",
            "/temperature | 0 | Unknown",
            "/temperature?location=Office | 0 | Office",
            "/temperature/1?sensorId=2&sensor_id=3 | 1 | Living Room",
            "/temperature?sensorId=2&sensor_id=3 | 2 | Bedroom",
            "/temperature/42?location=Office | 42 | Office"
    })
    void resolvesSensorAndReturnsCompatibleJson(String path, String sensorId, String location) throws Exception {
        Instant before = Instant.now();
        String body = mvc.perform(get(path))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(header().string("Cache-Control", "no-store"))
                .andExpect(jsonPath("$.sensor_id").value(sensorId))
                .andExpect(jsonPath("$.location").value(location))
                .andExpect(jsonPath("$.unit").value("°C"))
                .andExpect(jsonPath("$.status").value("active"))
                .andExpect(jsonPath("$.sensor_type").value("temperature"))
                .andExpect(jsonPath("$.description").isNotEmpty())
                .andReturn().getResponse().getContentAsString(java.nio.charset.StandardCharsets.UTF_8);
        JsonNode reading = objectMapper.readTree(body);
        assertThat(reading.get("value").decimalValue()).isBetween(
                new java.math.BigDecimal("15.00"), new java.math.BigDecimal("30.00"));
        assertThat(Instant.parse(reading.get("timestamp").asText())).isBetween(before, Instant.now());
    }

    @Test
    void preservesUnicodeAndSpecialCharactersInLocation() throws Exception {
        mvc.perform(get("/temperature").param("location", "Спальня & кабинет #1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.location").value("Спальня & кабинет #1"))
                .andExpect(jsonPath("$.sensor_id").value("0"));
    }

    @Test
    void exposesHealthAndRejectsUnsupportedRoutesAndMethods() throws Exception {
        mvc.perform(get("/health"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("ok"));
        mvc.perform(post("/temperature")).andExpect(status().isMethodNotAllowed());
        mvc.perform(get("/missing")).andExpect(status().isNotFound());
    }
}
