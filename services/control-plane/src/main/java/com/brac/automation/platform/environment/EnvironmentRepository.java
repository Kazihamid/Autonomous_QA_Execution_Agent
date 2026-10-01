package com.brac.automation.platform.environment;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
public interface EnvironmentRepository extends JpaRepository<EnvironmentEntity, UUID> {
    List<EnvironmentEntity> findByApplicationIdOrderByNameAsc(UUID applicationId);
    Optional<EnvironmentEntity> findByIdAndApplicationId(UUID id, UUID applicationId);
    boolean existsByApplicationIdAndNameIgnoreCase(UUID applicationId, String name);
    boolean existsByApplicationIdAndNameIgnoreCaseAndIdNot(UUID applicationId, String name, UUID id);
    long countByApplicationId(UUID applicationId);
}
