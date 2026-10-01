package com.brac.automation.platform.application;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema = "core", name = "application")
public class ApplicationEntity {
    @Id private UUID id;
    @Column(name="workspace_id", nullable=false) private UUID workspaceId;
    @Column(nullable=false) private String name;
    private String description;
    @Column(nullable=false) private String status;
    @Column(name="created_by", nullable=false) private UUID createdBy;
    @Column(name="created_at", nullable=false) private Instant createdAt;
    @Column(name="updated_at", nullable=false) private Instant updatedAt;
    protected ApplicationEntity() {}
    public ApplicationEntity(UUID workspaceId, String name, String description, UUID createdBy) {
        this.id=UUID.randomUUID(); this.workspaceId=workspaceId; this.name=name; this.description=description; this.status="ACTIVE";
        this.createdBy=createdBy; this.createdAt=Instant.now(); this.updatedAt=this.createdAt;
    }
    public void update(String name, String description, String status) { this.name=name; this.description=description; this.status=status; this.updatedAt=Instant.now(); }
    public UUID getId(){return id;} public UUID getWorkspaceId(){return workspaceId;} public String getName(){return name;}
    public String getDescription(){return description;} public String getStatus(){return status;} public Instant getCreatedAt(){return createdAt;}
}
