package com.brac.automation.platform.recorder;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema="core", name="scenario_version")
public class ScenarioVersionEntity {
    @Id private UUID id;
    @Column(name="scenario_id", nullable=false) private UUID scenarioId;
    @Column(name="version_no", nullable=false) private int versionNo;
    @Column(name="source_recording_session_id") private UUID sourceRecordingSessionId;
    @Column(name="automation_ir", nullable=false, columnDefinition="text") private String automationIr;
    @Column(name="created_by", nullable=false) private UUID createdBy;
    @Column(name="created_at", nullable=false) private Instant createdAt;

    protected ScenarioVersionEntity() {}
    public ScenarioVersionEntity(UUID scenarioId, int versionNo, UUID sourceRecordingSessionId, String automationIr, UUID createdBy) {
        this.id=UUID.randomUUID(); this.scenarioId=scenarioId; this.versionNo=versionNo; this.sourceRecordingSessionId=sourceRecordingSessionId;
        this.automationIr=automationIr; this.createdBy=createdBy; this.createdAt=Instant.now();
    }
    public UUID getId(){return id;} public UUID getScenarioId(){return scenarioId;} public int getVersionNo(){return versionNo;}
    public UUID getSourceRecordingSessionId(){return sourceRecordingSessionId;} public String getAutomationIr(){return automationIr;} public Instant getCreatedAt(){return createdAt;}
}
