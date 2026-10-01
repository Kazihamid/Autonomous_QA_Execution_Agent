package com.brac.automation.platform.application;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
public interface ApplicationRepository extends JpaRepository<ApplicationEntity, UUID> {
    List<ApplicationEntity> findByWorkspaceIdOrderByNameAsc(UUID workspaceId);
    Optional<ApplicationEntity> findByIdAndWorkspaceId(UUID id, UUID workspaceId);
    boolean existsByWorkspaceIdAndNameIgnoreCase(UUID workspaceId, String name);
    boolean existsByWorkspaceIdAndNameIgnoreCaseAndIdNot(UUID workspaceId, String name, UUID id);
}
