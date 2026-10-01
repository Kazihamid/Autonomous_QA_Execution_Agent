package com.brac.automation.platform.workspace;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
public interface WorkspaceRepository extends JpaRepository<Workspace, UUID> {
    boolean existsByWorkspaceKeyIgnoreCase(String key);
    boolean existsByWorkspaceKeyIgnoreCaseAndIdNot(String key, UUID id);
    Optional<Workspace> findByIdAndStatus(UUID id, String status);
}
