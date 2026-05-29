FROM eclipse-temurin:21-jre

WORKDIR /app

COPY target/app.jar /app/app.jar

EXPOSE 8080

RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
