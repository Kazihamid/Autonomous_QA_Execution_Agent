package com.brac.automation.platform.recorder;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ScenarioVersionRepository extends JpaRepository<ScenarioVersionEntity, UUID> {
    Optional<ScenarioVersionEntity> findFirstByScenarioIdOrderByVersionNoDesc(UUID scenarioId);
    Optional<ScenarioVersionEntity> findFirstBySourceRecordingSessionId(UUID sourceRecordingSessionId);
    long deleteByScenarioId(UUID scenarioId);
}
