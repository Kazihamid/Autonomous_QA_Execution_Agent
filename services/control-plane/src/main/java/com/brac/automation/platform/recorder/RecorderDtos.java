package com.brac.automation.platform.recorder;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.UUID;
import tools.jackson.databind.JsonNode;

public final class RecorderDtos {
    private RecorderDtos() {}

    public record CreateSessionRequest(
        @NotBlank @Size(max=200) String scenarioName,
        @Size(max=120) String moduleName,
        @Size(max=120) String featureName
    ) {}

    public record AssertionRequest(
        @NotBlank @Size(max=1000) String selector,
        @NotBlank @Pattern(regexp="visible|hidden|text|value|checked") String assertionType,
        @Size(max=2000) String expected
    ) {}

    public record PasteRequest(@NotBlank @Size(max=2000) String text) {}

    public record CheckpointRequest(@NotBlank @Size(max=500) String description) {}

    public record SessionResponse(
        UUID id,
        UUID workspaceId,
        UUID applicationId,
        UUID environmentId,
        String workerSessionId,
        String scenarioName,
        String moduleName,
        String featureName,
        String status,
        String startUrl,
        String browser,
        int rawEventCount,
        int semanticActionCount,
        String error,
        JsonNode ir,
        Instant createdAt,
        Instant updatedAt
    ) {}

    public record ScenarioResponse(
        UUID id,
        UUID workspaceId,
        UUID applicationId,
        String moduleName,
        String featureName,
        String name,
        String status,
        int currentVersion,
        Integer executionOrder,
        Instant createdAt
    ) {}

    public record CloneScenarioRequest(
        @jakarta.validation.constraints.NotBlank @Size(max=200) String name,
        @Size(max=120) String moduleName,
        @Size(max=120) String featureName,
        java.util.Map<String,String> parameters,
        java.util.Map<String,String> secretReferences
    ) {}

    public record UpdateScenarioRequest(
        @jakarta.validation.constraints.NotBlank @Size(max=200) String name,
        @Size(max=120) String moduleName,
        @Size(max=120) String featureName,
        java.util.Map<String,String> parameters,
        java.util.Map<String,String> secretReferences
    ) {}

    public record ReorderRequest(@jakarta.validation.constraints.NotEmpty @Size(max=500) java.util.List<UUID> scenarioIds) {}

    public record ScenarioDetailResponse(ScenarioResponse scenario, int versionNo, UUID sourceRecordingSessionId, JsonNode automationIr, Instant versionCreatedAt) {}
}
