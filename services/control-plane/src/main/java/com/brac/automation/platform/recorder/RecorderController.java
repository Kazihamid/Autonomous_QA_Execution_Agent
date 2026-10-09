package com.brac.automation.platform.recorder;

import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/workspaces/{workspaceId}/applications/{applicationId}")
public class RecorderController {
    private final RecorderService service;
    private final ScenarioRecoveryService recovery;
    public RecorderController(RecorderService service, ScenarioRecoveryService recovery) { this.service=service; this.recovery=recovery; }

    @PostMapping("/environments/{environmentId}/recording-sessions") @ResponseStatus(HttpStatus.CREATED)
    public RecorderDtos.SessionResponse create(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID environmentId,
                                                @Valid @RequestBody RecorderDtos.CreateSessionRequest request) {
        return service.create(workspaceId, applicationId, environmentId, request);
    }

    @GetMapping("/recording-sessions")
    public List<RecorderDtos.SessionResponse> listSessions(@PathVariable UUID workspaceId, @PathVariable UUID applicationId) {
        return service.listSessions(workspaceId, applicationId);
    }

    @GetMapping("/recording-sessions/{sessionId}")
    public RecorderDtos.SessionResponse getSession(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId) {
        return service.getSession(workspaceId, applicationId, sessionId);
    }

    @PostMapping("/recording-sessions/{sessionId}/start")
    public RecorderDtos.SessionResponse start(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId) {
        return service.command(workspaceId, applicationId, sessionId, "start");
    }

    @PostMapping("/recording-sessions/{sessionId}/pause")
    public RecorderDtos.SessionResponse pause(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId) {
        return service.command(workspaceId, applicationId, sessionId, "pause");
    }

    @PostMapping("/recording-sessions/{sessionId}/resume")
    public RecorderDtos.SessionResponse resume(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId) {
        return service.command(workspaceId, applicationId, sessionId, "resume");
    }

    @PostMapping("/recording-sessions/{sessionId}/cancel")
    public RecorderDtos.SessionResponse cancel(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId) {
        return service.command(workspaceId, applicationId, sessionId, "cancel");
    }

    @PostMapping("/recording-sessions/{sessionId}/assertions") @ResponseStatus(HttpStatus.NO_CONTENT)
    public void assertion(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId,
                          @Valid @RequestBody RecorderDtos.AssertionRequest request) {
        service.addAssertion(workspaceId, applicationId, sessionId, request);
    }

    @PostMapping("/recording-sessions/{sessionId}/checkpoints") @ResponseStatus(HttpStatus.NO_CONTENT)
    public void checkpoint(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId,
                           @Valid @RequestBody RecorderDtos.CheckpointRequest request) {
        service.addCheckpoint(workspaceId, applicationId, sessionId, request);
    }

    @PostMapping("/recording-sessions/{sessionId}/paste") @ResponseStatus(HttpStatus.NO_CONTENT)
    public void paste(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId,
                      @Valid @RequestBody RecorderDtos.PasteRequest request) {
        service.pasteText(workspaceId, applicationId, sessionId, request);
    }

    @PostMapping("/recording-sessions/{sessionId}/finish")
    public RecorderDtos.SessionResponse finish(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId) {
        return service.finish(workspaceId, applicationId, sessionId);
    }

    @PostMapping("/recording-sessions/{sessionId}/scenarios") @ResponseStatus(HttpStatus.CREATED)
    public RecorderDtos.ScenarioResponse saveScenario(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId) {
        RecorderDtos.ScenarioResponse result = service.saveScenario(workspaceId, applicationId, sessionId);
        recovery.snapshotQuietly(workspaceId, applicationId);
        return result;
    }

    @GetMapping("/scenarios")
    public List<RecorderDtos.ScenarioResponse> listScenarios(@PathVariable UUID workspaceId, @PathVariable UUID applicationId) {
        return service.listScenarios(workspaceId, applicationId);
    }

    @PutMapping("/scenarios/order")
    public List<RecorderDtos.ScenarioResponse> reorderScenarios(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @Valid @RequestBody RecorderDtos.ReorderRequest request) {
        return service.reorderScenarios(workspaceId, applicationId, request);
    }

    @PostMapping("/scenarios/{scenarioId}/clone") @ResponseStatus(HttpStatus.CREATED)
    public RecorderDtos.ScenarioResponse cloneScenario(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID scenarioId,
            @Valid @RequestBody RecorderDtos.CloneScenarioRequest request) {
        RecorderDtos.ScenarioResponse result = service.cloneScenario(workspaceId, applicationId, scenarioId, request);
        recovery.snapshotQuietly(workspaceId, applicationId);
        return result;
    }

    @GetMapping("/scenarios/{scenarioId}")
    public RecorderDtos.ScenarioDetailResponse getScenario(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID scenarioId) {
        return service.getScenario(workspaceId, applicationId, scenarioId);
    }

    @PutMapping("/scenarios/{scenarioId}")
    public RecorderDtos.ScenarioResponse updateScenario(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID scenarioId,
            @Valid @RequestBody RecorderDtos.UpdateScenarioRequest request) {
        RecorderDtos.ScenarioResponse result = service.updateScenario(workspaceId, applicationId, scenarioId, request);
        recovery.snapshotQuietly(workspaceId, applicationId);
        return result;
    }

    @DeleteMapping("/scenarios/{scenarioId}") @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteScenario(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID scenarioId) {
        service.deleteScenario(workspaceId, applicationId, scenarioId);
        recovery.snapshotQuietly(workspaceId, applicationId);
    }
}
