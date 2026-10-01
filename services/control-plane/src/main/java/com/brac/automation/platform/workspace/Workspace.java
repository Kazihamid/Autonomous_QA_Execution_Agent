package com.brac.automation.platform.workspace;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema = "core", name = "workspace")
public class Workspace {
    @Id private UUID id;
    @Column(name = "workspace_key", nullable = false, unique = true) private String workspaceKey;
    @Column(nullable = false) private String name;
    private String description;
    @Column(nullable = false) private String status;
    @Column(name = "created_by") private UUID createdBy;
    @Column(name = "created_at", nullable = false) private Instant createdAt;
    @Column(name = "updated_at", nullable = false) private Instant updatedAt;

    protected Workspace() {}
    public Workspace(String key, String name, String description, UUID createdBy) {
        this.id = UUID.randomUUID(); this.workspaceKey = key; this.name = name; this.description = description;
        this.status = "ACTIVE"; this.createdBy = createdBy; this.createdAt = Instant.now(); this.updatedAt = this.createdAt;
    }
    public UUID getId() { return id; }
    public String getWorkspaceKey() { return workspaceKey; }
    public String getName() { return name; }
    public String getDescription() { return description; }
    public String getStatus() { return status; }
    public void update(String key, String name, String description) {
        this.workspaceKey = key; this.name = name; this.description = description; this.updatedAt = Instant.now();
    }
    public void archive() { this.status = "DELETED"; this.updatedAt = Instant.now(); }
    public Instant getCreatedAt() { return createdAt; }
}
