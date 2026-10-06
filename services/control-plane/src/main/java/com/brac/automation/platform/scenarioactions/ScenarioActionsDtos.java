package com.brac.automation.platform.scenarioactions;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.UUID;

public final class ScenarioActionsDtos {
    private ScenarioActionsDtos() {}

    public record BulkExportRequest(
        @NotEmpty @Size(max = 50) List<UUID> scenarioIds,
        @NotBlank String target) {}

    public record RunRequest(
        @NotEmpty @Size(max = 25) List<UUID> scenarioIds,
        Boolean stopOnFailure,
        UUID environmentId) {}

    public record RunResult(
        UUID scenarioId,
        String scenarioName,
        String status,
        Integer exitCode,
        long durationMs,
        String stdout,
        String stderr) {}

    public record BulkRunResponse(
        int total,
        int passed,
        int failed,
        int skipped,
        List<RunResult> results) {}

    public record RunItemView(
        UUID scenarioId,
        String scenarioName,
        String status,
        int currentStep,
        int totalSteps,
        String currentAction,
        java.time.Instant startedAt,
        long durationMs,
        String output,
        String message) {}

    public record RunJobView(
        UUID jobId,
        String status,
        UUID environmentId,
        String environmentName,
        String baseUrl,
        boolean stopOnFailure,
        java.time.Instant startedAt,
        java.time.Instant finishedAt,
        int total,
        int completed,
        int passed,
        int failed,
        int skipped,
        List<RunItemView> items) {}
}
