package com.brac.automation.platform.recorder;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TestScenarioRepository extends JpaRepository<TestScenarioEntity, UUID> {
    List<TestScenarioEntity> findByWorkspaceIdAndApplicationIdOrderByExecutionOrderAscModuleNameAscFeatureNameAscNameAsc(UUID workspaceId, UUID applicationId);
    Optional<TestScenarioEntity> findByIdAndWorkspaceIdAndApplicationId(UUID id, UUID workspaceId, UUID applicationId);
    /** Counts deleted scenarios too, so an application that still holds recoverable scenarios cannot be deleted. */
    @Query(value = "select count(*) from core.test_scenario where application_id = :applicationId", nativeQuery = true)
    long countByApplicationId(@Param("applicationId") UUID applicationId);

    /** Moves a scenario to "recently deleted"; its versions and generated code are kept so it can be restored. */
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query(value = "update core.test_scenario set status = 'DELETED', deleted_at = now(), deleted_by = :by, updated_at = now() where id = :id", nativeQuery = true)
    int softDelete(@Param("id") UUID id, @Param("by") UUID by);
}
