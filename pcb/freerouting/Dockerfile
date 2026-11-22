# Freerouting, headless, for the rev 3 board (see pcb/README.md, Routing).
#   docker compose run --rm freerouting -de board.dsn -do board.ses -mp 30
# Freerouting 2.5.0 is built for Java 25.  The jar is pinned by version and checksum.
FROM eclipse-temurin:25.0.4_7-jre
ADD --checksum=sha256:f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7 \
    https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar /opt/freerouting.jar
WORKDIR /work
ENTRYPOINT ["java", "-Djava.awt.headless=true", "-jar", "/opt/freerouting.jar", "--gui.enabled=false", "--api_server.enabled=false"]
