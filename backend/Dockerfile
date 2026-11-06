# syntax=docker/dockerfile:1
ARG GO_VERSION=1.26
FROM golang:${GO_VERSION}-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN for c in api worker migrate seed healthcheck; do \
      CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/$c ./cmd/$c; done

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/ /
USER nonroot:nonroot
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=4s --retries=5 CMD ["/healthcheck"]
ENTRYPOINT ["/api"]
