package com.brac.automation.platform.recorder;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RecordingSessionRepository extends JpaRepository<RecordingSessionEntity, UUID> {
    Optional<RecordingSessionEntity> findByIdAndWorkspaceIdAndApplicationId(UUID id, UUID workspaceId, UUID applicationId);
    List<RecordingSessionEntity> findByWorkspaceIdAndApplicationIdOrderByCreatedAtDesc(UUID workspaceId, UUID applicationId);
    long countByEnvironmentId(UUID environmentId);
    long countByApplicationId(UUID applicationId);
}
