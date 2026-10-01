package com.brac.automation.platform.workspace;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema = "core", name = "workspace_member")
public class WorkspaceMember {
    @Id private UUID id;
    @Column(name = "workspace_id", nullable = false) private UUID workspaceId;
    @Column(name = "user_id", nullable = false) private UUID userId;
    @Enumerated(EnumType.STRING) @Column(nullable = false) private WorkspaceRole role;
    @Column(nullable = false) private boolean active;
    @Column(name = "created_at", nullable = false) private Instant createdAt;
    @Column(name = "updated_at", nullable = false) private Instant updatedAt;

    protected WorkspaceMember() {}
    public WorkspaceMember(UUID workspaceId, UUID userId, WorkspaceRole role) {
        this.id = UUID.randomUUID(); this.workspaceId = workspaceId; this.userId = userId; this.role = role;
        this.active = true; this.createdAt = Instant.now(); this.updatedAt = this.createdAt;
    }
    public void changeRole(WorkspaceRole role) { this.role = role; this.updatedAt = Instant.now(); }
    public void deactivate() { this.active = false; this.updatedAt = Instant.now(); }
    public UUID getId() { return id; }
    public UUID getWorkspaceId() { return workspaceId; }
    public UUID getUserId() { return userId; }
    public WorkspaceRole getRole() { return role; }
    public boolean isActive() { return active; }
}
