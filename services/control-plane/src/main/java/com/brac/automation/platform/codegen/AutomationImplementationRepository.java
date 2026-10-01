package com.brac.automation.platform.codegen;
import java.util.List;import java.util.Optional;import java.util.UUID;import org.springframework.data.jpa.repository.JpaRepository;
public interface AutomationImplementationRepository extends JpaRepository<AutomationImplementationEntity, UUID> {
    List<AutomationImplementationEntity> findByWorkspaceIdAndApplicationIdAndScenarioIdOrderByCreatedAtDesc(UUID workspaceId, UUID applicationId, UUID scenarioId);
    Optional<AutomationImplementationEntity> findByIdAndWorkspaceIdAndApplicationIdAndScenarioId(UUID id, UUID workspaceId, UUID applicationId, UUID scenarioId);
    long countByScenarioVersionIdAndTargetProfile(UUID scenarioVersionId, String targetProfile);
    long deleteByScenarioId(UUID scenarioId);
}
