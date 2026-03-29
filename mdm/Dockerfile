FROM micromdm/micromdm:latest

EXPOSE 80 443

ENTRYPOINT ["micromdm", "serve", \
    "-server-url", "${MDM_SERVER_URL}", \
    "-api-key", "${MDM_API_KEY}", \
    "-tls-cert", "/certs/server.crt", \
    "-tls-key", "/certs/server.key"]
