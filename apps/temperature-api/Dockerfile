FROM gradle:8.14.3-jdk21-alpine AS builder
USER root
ENV GRADLE_USER_HOME=/root/.gradle
WORKDIR /src
COPY build.gradle.kts settings.gradle.kts ./
COPY src ./src
RUN --mount=type=cache,target=/root/.gradle gradle --no-daemon --console=plain build

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=builder /src/build/libs/temperature-api.jar /app/temperature-api.jar
USER 10001:10001
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "/app/temperature-api.jar"]
