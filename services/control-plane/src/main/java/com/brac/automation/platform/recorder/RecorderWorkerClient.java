package com.brac.automation.platform.recorder;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Component
public class RecorderWorkerClient {
    private final HttpClient http;
    private final ObjectMapper mapper;
    private final String baseUrl;

    public RecorderWorkerClient(ObjectMapper mapper, @Value("${platform.recorder.base-url}") String baseUrl) {
        this.mapper = mapper;
        this.baseUrl = normalizeBaseUrl(baseUrl);
        this.http = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    }

    public WorkerSession create(String startUrl, String browser, String scenarioName) {
        try {
            return postJson(
                "/api/v1/sessions",
                new CreateRequest(startUrl, browser.toLowerCase(), false, scenarioName),
                WorkerSession.class
            );
        } catch (RecorderWorkerException ex) {
            throw new RecorderWorkerException(
                "Recorder worker could not create the managed browser session: " + ex.getMessage(), ex);
        }
    }

    public WorkerSession command(String workerSessionId, String command) {
        try {
            return postEmpty(
                "/api/v1/sessions/" + workerSessionId + "/" + command,
                WorkerSession.class
            );
        } catch (RecorderWorkerException ex) {
            throw new RecorderWorkerException(
                "Recorder worker command failed: " + command + ". " + ex.getMessage(), ex);
        }
    }

    public void addAssertion(String workerSessionId, String selector, String assertionType, String expected) {
        try {
            postJsonNoResponse(
                "/api/v1/sessions/" + workerSessionId + "/assertions",
                new AssertionRequest(selector, assertionType, expected)
            );
        } catch (RecorderWorkerException ex) {
            throw new RecorderWorkerException(
                "Recorder assertion could not be added: " + ex.getMessage(), ex);
        }
    }

    public void addCheckpoint(String workerSessionId, String description) {
        try {
            postJsonNoResponse(
                "/api/v1/sessions/" + workerSessionId + "/checkpoints",
                new CheckpointRequest(description)
            );
        } catch (RecorderWorkerException ex) {
            throw new RecorderWorkerException(
                "Recorder checkpoint could not be added: " + ex.getMessage(), ex);
        }
    }

    public void pasteText(String workerSessionId, String text) {
        try {
            postJsonNoResponse("/api/v1/sessions/" + workerSessionId + "/paste", new PasteRequest(text));
        } catch (RecorderWorkerException ex) {
            // Never echo the text: it may be a password.
            throw new RecorderWorkerException("Text could not be pasted into the managed browser. Click the field in the browser first. " + String.valueOf(ex.getMessage()).replace(text, "***"), ex);
        }
    }

    public FinishResponse finish(String workerSessionId) {
        try {
            return postEmpty(
                "/api/v1/sessions/" + workerSessionId + "/finish",
                FinishResponse.class
            );
        } catch (RecorderWorkerException ex) {
            throw new RecorderWorkerException(
                "Recorder worker could not finish the session: " + ex.getMessage(), ex);
        }
    }

    private <T> T postJson(String path, Object payload, Class<T> responseType) {
        try {
            String json = mapper.writeValueAsString(payload);
            HttpRequest request = request(path)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                .build();
            return send(request, responseType);
        } catch (RecorderWorkerException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new RecorderWorkerException("Failed to serialize/send JSON request: " + ex.getMessage(), ex);
        }
    }

    private void postJsonNoResponse(String path, Object payload) {
        try {
            String json = mapper.writeValueAsString(payload);
            HttpRequest request = request(path)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                .build();
            sendNoResponse(request);
        } catch (RecorderWorkerException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new RecorderWorkerException("Failed to serialize/send JSON request: " + ex.getMessage(), ex);
        }
    }

    private <T> T postEmpty(String path, Class<T> responseType) {
        try {
            HttpRequest request = request(path)
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();
            return send(request, responseType);
        } catch (RecorderWorkerException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new RecorderWorkerException("Failed to send recorder request: " + ex.getMessage(), ex);
        }
    }

    private HttpRequest.Builder request(String path) {
        return HttpRequest.newBuilder(URI.create(baseUrl + path))
            .version(HttpClient.Version.HTTP_1_1)
            .timeout(Duration.ofSeconds(60))
            .header("Accept", "application/json");
    }

    private <T> T send(HttpRequest request, Class<T> responseType) {
        try {
            HttpResponse<String> response = http.send(
                request,
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)
            );
            ensureSuccess(response);
            return mapper.readValue(response.body(), responseType);
        } catch (RecorderWorkerException ex) {
            throw ex;
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new RecorderWorkerException("Recorder request was interrupted.", ex);
        } catch (Exception ex) {
            throw new RecorderWorkerException("Recorder response could not be processed: " + ex.getMessage(), ex);
        }
    }

    private void sendNoResponse(HttpRequest request) {
        try {
            HttpResponse<String> response = http.send(
                request,
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)
            );
            ensureSuccess(response);
        } catch (RecorderWorkerException ex) {
            throw ex;
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new RecorderWorkerException("Recorder request was interrupted.", ex);
        } catch (Exception ex) {
            throw new RecorderWorkerException("Recorder response could not be processed: " + ex.getMessage(), ex);
        }
    }

    private void ensureSuccess(HttpResponse<String> response) {
        int status = response.statusCode();
        if (status < 200 || status >= 300) {
            String body = response.body() == null ? "" : response.body();
            throw new RecorderWorkerException("HTTP " + status + ": " + body);
        }
    }

    private static String normalizeBaseUrl(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("platform.recorder.base-url must not be blank");
        }
        String trimmed = value.trim();
        while (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed;
    }

    public record CreateRequest(String startUrl, String browser, boolean headless, String scenarioName) {}
    public record AssertionRequest(String selector, String assertionType, String expected) {}
    public record CheckpointRequest(String description) {}
    public record PasteRequest(String text) {}
    public record WorkerSession(String sessionId, String startUrl, String scenarioName, String browser, boolean headless, String status, String createdAt, String error) {}
    public record FinishResponse(WorkerSession session, int rawEventCount, int semanticActionCount, List<String> errors, JsonNode ir) {}
}