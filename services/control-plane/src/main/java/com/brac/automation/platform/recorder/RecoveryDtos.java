package com.brac.automation.platform.recorder;

import java.util.UUID;

public final class RecoveryDtos {
    private RecoveryDtos() {}

    public record DeletedScenario(UUID id, String moduleName, String featureName, String name, int currentVersion, String deletedAt) {}

    public record VersionInfo(int versionNo, String createdAt, UUID sourceRecordingSessionId, boolean current) {}

    public record RecoverableRecording(UUID sessionId, String scenarioName, String moduleName, String featureName, String recordedAt) {}

    public record ImportResult(int restored, int created, int copied, int versionsAdded, int skipped) {}
}
