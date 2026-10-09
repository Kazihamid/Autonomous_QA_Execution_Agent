package com.brac.automation.platform.recorder;

import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.JsonNode;

@RestController
@RequestMapping("/api/v1/workspaces/{workspaceId}/applications/{applicationId}")
public class ScenarioRecoveryController {
    private final ScenarioRecoveryService recovery;
    private final RecorderService recorder;

    public ScenarioRecoveryController(ScenarioRecoveryService recovery, RecorderService recorder) { this.recovery = recovery; this.recorder = recorder; }

    @GetMapping("/scenarios/deleted")
    public List<RecoveryDtos.DeletedScenario> deleted(@PathVariable UUID workspaceId, @PathVariable UUID applicationId) {
        return recovery.listDeleted(workspaceId, applicationId);
    }

    @PostMapping("/scenarios/{scenarioId}/restore")
    public RecorderDtos.ScenarioResponse restore(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID scenarioId) {
        RecorderDtos.ScenarioResponse result = recovery.restore(workspaceId, applicationId, scenarioId);
        recovery.snapshotQuietly(workspaceId, applicationId);
        return result;
    }

    @DeleteMapping("/scenarios/{scenarioId}/permanent") @ResponseStatus(HttpStatus.NO_CONTENT)
    public void purgeOne(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID scenarioId) {
        recovery.purgeDeleted(workspaceId, applicationId, scenarioId);
        recovery.snapshotQuietly(workspaceId, applicationId);
    }

    @DeleteMapping("/scenarios/deleted")
    public java.util.Map<String, Integer> purgeAll(@PathVariable UUID workspaceId, @PathVariable UUID applicationId) {
        int removed = recovery.purgeDeleted(workspaceId, applicationId, null);
        recovery.snapshotQuietly(workspaceId, applicationId);
        return java.util.Map.of("removed", removed);
    }

    @GetMapping("/scenarios/{scenarioId}/versions")
    public List<RecoveryDtos.VersionInfo> versions(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID scenarioId) {
        return recovery.listVersions(workspaceId, applicationId, scenarioId);
    }

    @PostMapping("/scenarios/{scenarioId}/versions/{versionNo}/restore")
    public RecorderDtos.ScenarioResponse restoreVersion(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID scenarioId, @PathVariable int versionNo) {
        RecorderDtos.ScenarioResponse result = recovery.restoreVersion(workspaceId, applicationId, scenarioId, versionNo);
        recovery.snapshotQuietly(workspaceId, applicationId);
        return result;
    }

    @GetMapping("/scenarios/recoverable-recordings")
    public List<RecoveryDtos.RecoverableRecording> recoverable(@PathVariable UUID workspaceId, @PathVariable UUID applicationId) {
        return recovery.recoverableRecordings(workspaceId, applicationId);
    }

    @PostMapping("/recording-sessions/{sessionId}/recover") @ResponseStatus(HttpStatus.CREATED)
    public RecorderDtos.ScenarioResponse recoverRecording(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId) {
        RecorderDtos.ScenarioResponse result = recorder.saveScenario(workspaceId, applicationId, sessionId);
        recovery.snapshotQuietly(workspaceId, applicationId);
        return result;
    }

    @PostMapping("/recording-sessions/{sessionId}/dismiss") @ResponseStatus(HttpStatus.NO_CONTENT)
    public void dismissRecording(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID sessionId) {
        recovery.dismissRecording(workspaceId, applicationId, sessionId);
    }

    @GetMapping("/scenarios/backup")
    public JsonNode backup(@PathVariable UUID workspaceId, @PathVariable UUID applicationId) {
        return recovery.backup(workspaceId, applicationId);
    }

    @PostMapping("/scenarios/backup/import")
    public RecoveryDtos.ImportResult importBackup(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @RequestBody JsonNode document) {
        RecoveryDtos.ImportResult result = recovery.importBackup(workspaceId, applicationId, document);
        recovery.snapshotQuietly(workspaceId, applicationId);
        return result;
    }
}
