package com.brac.automation.platform.recorder;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TestScenarioRepository extends JpaRepository<TestScenarioEntity, UUID> {
    List<TestScenarioEntity> findByWorkspaceIdAndApplicationIdOrderByExecutionOrderAscModuleNameAscFeatureNameAscNameAsc(UUID workspaceId, UUID applicationId);
    Optional<TestScenarioEntity> findByIdAndWorkspaceIdAndApplicationId(UUID id, UUID workspaceId, UUID applicationId);
    long countByApplicationId(UUID applicationId);
}
