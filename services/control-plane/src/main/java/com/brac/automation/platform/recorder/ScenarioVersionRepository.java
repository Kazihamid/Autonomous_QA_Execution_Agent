package com.brac.automation.platform.recorder;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ScenarioVersionRepository extends JpaRepository<ScenarioVersionEntity, UUID> {
    Optional<ScenarioVersionEntity> findFirstByScenarioIdOrderByVersionNoDesc(UUID scenarioId);
    Optional<ScenarioVersionEntity> findFirstBySourceRecordingSessionId(UUID sourceRecordingSessionId);
    List<ScenarioVersionEntity> findByScenarioIdOrderByVersionNoDesc(UUID scenarioId);
    Optional<ScenarioVersionEntity> findByScenarioIdAndVersionNo(UUID scenarioId, int versionNo);
    long deleteByScenarioId(UUID scenarioId);
}
