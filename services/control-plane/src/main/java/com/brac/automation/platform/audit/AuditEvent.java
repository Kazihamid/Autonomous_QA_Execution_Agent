package com.brac.automation.platform.audit;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema = "audit", name = "audit_event")
public class AuditEvent {
    @Id private UUID id;
    @Column(name = "workspace_id") private UUID workspaceId;
    @Column(name = "actor_user_id") private UUID actorUserId;
    @Column(nullable = false) private String action;
    @Column(name = "resource_type", nullable = false) private String resourceType;
    @Column(name = "resource_id") private UUID resourceId;
    @Column(nullable = false) private String outcome;
    @Column(name = "metadata_text") private String metadataText;
    @Column(name = "occurred_at", nullable = false) private Instant occurredAt;
    protected AuditEvent() {}
    public AuditEvent(UUID workspaceId, UUID actorUserId, String action, String resourceType, UUID resourceId, String outcome, String metadataText) {
        this.id = UUID.randomUUID(); this.workspaceId = workspaceId; this.actorUserId = actorUserId; this.action = action;
        this.resourceType = resourceType; this.resourceId = resourceId; this.outcome = outcome; this.metadataText = metadataText;
        this.occurredAt = Instant.now();
    }
}
