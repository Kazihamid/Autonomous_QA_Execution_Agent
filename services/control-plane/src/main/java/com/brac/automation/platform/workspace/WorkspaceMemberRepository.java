package com.brac.automation.platform.workspace;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
public interface WorkspaceMemberRepository extends JpaRepository<WorkspaceMember, UUID> {
    Optional<WorkspaceMember> findByWorkspaceIdAndUserIdAndActiveTrue(UUID workspaceId, UUID userId);
    List<WorkspaceMember> findByUserIdAndActiveTrue(UUID userId);
    List<WorkspaceMember> findByWorkspaceIdAndActiveTrueOrderByCreatedAtAsc(UUID workspaceId);
}
