package com.brac.automation.platform.scenarioactions;

import com.brac.automation.platform.codegen.CodeGeneratorDtos;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Component
public class RunnerClient {
    private final HttpClient http;
    private final ObjectMapper mapper;
    private final String baseUrl;

    public RunnerClient(ObjectMapper mapper, @Value("${platform.runner.base-url}") String baseUrl) {
        this.mapper = mapper;
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.http = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    }

    public ScenarioActionsDtos.RunResult run(UUID scenarioId, String scenarioName, String targetBaseUrl,
            List<CodeGeneratorDtos.GeneratedFile> files) {
        try {
            var payload = mapper.createObjectNode();
            payload.put("scenarioId", scenarioId.toString());
            payload.put("scenarioName", scenarioName);
            payload.put("baseUrl", targetBaseUrl);
            payload.put("timeoutSeconds", 120);
            payload.set("files", mapper.valueToTree(files));
            String body = mapper.writeValueAsString(payload);
            HttpRequest req = HttpRequest.newBuilder(URI.create(baseUrl + "/api/v1/run"))
                .version(HttpClient.Version.HTTP_1_1)
                .timeout(Duration.ofSeconds(150))
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
            HttpResponse<String> response = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                return new ScenarioActionsDtos.RunResult(scenarioId, scenarioName, "ERROR", null, 0,
                    "", "Runner HTTP " + response.statusCode() + ": " + response.body());
            }
            JsonNode node = mapper.readTree(response.body());
            return new ScenarioActionsDtos.RunResult(
                scenarioId,
                scenarioName,
                node.path("status").asText("ERROR"),
                node.path("exitCode").isNull() || node.path("exitCode").isMissingNode() ? null : node.path("exitCode").asInt(),
                node.path("durationMs").asLong(0),
                node.path("stdout").asText(""),
                node.path("stderr").asText("")
            );
        } catch (Exception ex) {
            if (ex instanceof InterruptedException) Thread.currentThread().interrupt();
            return new ScenarioActionsDtos.RunResult(scenarioId, scenarioName, "ERROR", null, 0, "", ex.getMessage());
        }
    }

    /** Snapshot of an asynchronous run on the runner service. */
    public record RunnerRunStatus(String status, Integer exitCode, long durationMs, String output,
            int currentStep, int totalSteps, String currentAction, String message) {
        public boolean terminal() { return !("QUEUED".equals(status) || "RUNNING".equals(status)); }
    }

    /** Starts an asynchronous run and returns the runner's run id. */
    public String start(UUID scenarioId, String scenarioName, String targetBaseUrl, int timeoutSeconds,
            List<CodeGeneratorDtos.GeneratedFile> files) throws Exception {
        var payload = mapper.createObjectNode();
        payload.put("scenarioId", scenarioId.toString());
        payload.put("scenarioName", scenarioName);
        payload.put("baseUrl", targetBaseUrl);
        payload.put("timeoutSeconds", timeoutSeconds);
        payload.set("files", mapper.valueToTree(files));
        HttpRequest req = HttpRequest.newBuilder(URI.create(baseUrl + "/api/v1/runs"))
            .version(HttpClient.Version.HTTP_1_1)
            .timeout(Duration.ofSeconds(30))
            .header("Content-Type", "application/json")
            .header("Accept", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(payload)))
            .build();
        HttpResponse<String> response = http.send(req, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IllegalStateException("Runner HTTP " + response.statusCode() + ": " + response.body());
        }
        String runId = mapper.readTree(response.body()).path("runId").asText("");
        if (runId.isBlank()) throw new IllegalStateException("Runner did not return a run id.");
        return runId;
    }

    public RunnerRunStatus poll(String runId) throws Exception {
        HttpRequest req = HttpRequest.newBuilder(URI.create(baseUrl + "/api/v1/runs/" + runId))
            .version(HttpClient.Version.HTTP_1_1)
            .timeout(Duration.ofSeconds(15))
            .header("Accept", "application/json")
            .GET()
            .build();
        HttpResponse<String> response = http.send(req, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IllegalStateException("Runner HTTP " + response.statusCode() + ": " + response.body());
        }
        JsonNode n = mapper.readTree(response.body());
        return new RunnerRunStatus(
            n.path("status").asText("ERROR"),
            n.path("exitCode").isNull() || n.path("exitCode").isMissingNode() ? null : n.path("exitCode").asInt(),
            n.path("durationMs").asLong(0),
            n.path("output").asText(""),
            n.path("currentStep").asInt(0),
            n.path("totalSteps").asInt(0),
            n.path("currentAction").asText(""),
            n.path("message").asText(""));
    }
}
