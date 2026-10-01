package com.brac.automation.platform.recorder;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema="core", name="recording_session")
public class RecordingSessionEntity {
    @Id private UUID id;
    @Column(name="workspace_id", nullable=false) private UUID workspaceId;
    @Column(name="application_id", nullable=false) private UUID applicationId;
    @Column(name="environment_id", nullable=false) private UUID environmentId;
    @Column(name="worker_session_id", nullable=false, unique=true) private String workerSessionId;
    @Column(name="scenario_name", nullable=false) private String scenarioName;
    @Column(name="module_name") private String moduleName;
    @Column(name="feature_name") private String featureName;
    @Column(nullable=false) private String status;
    @Column(name="start_url", nullable=false) private String startUrl;
    @Column(nullable=false) private String browser;
    @Column(name="raw_event_count", nullable=false) private int rawEventCount;
    @Column(name="semantic_action_count", nullable=false) private int semanticActionCount;
    @Column(name="ir_json", columnDefinition="text") private String irJson;
    @Column(name="error_text", columnDefinition="text") private String errorText;
    @Column(name="created_by", nullable=false) private UUID createdBy;
    @Column(name="created_at", nullable=false) private Instant createdAt;
    @Column(name="updated_at", nullable=false) private Instant updatedAt;

    protected RecordingSessionEntity() {}

    public RecordingSessionEntity(UUID workspaceId, UUID applicationId, UUID environmentId, String workerSessionId,
                                  String scenarioName, String moduleName, String featureName, String status,
                                  String startUrl, String browser, UUID createdBy) {
        this.id=UUID.randomUUID(); this.workspaceId=workspaceId; this.applicationId=applicationId; this.environmentId=environmentId;
        this.workerSessionId=workerSessionId; this.scenarioName=scenarioName; this.moduleName=moduleName; this.featureName=featureName;
        this.status=status; this.startUrl=startUrl; this.browser=browser; this.createdBy=createdBy;
        this.rawEventCount=0; this.semanticActionCount=0; this.createdAt=Instant.now(); this.updatedAt=this.createdAt;
    }

    public void updateWorkerStatus(String status, String error) {
        this.status=status; this.errorText=error; this.updatedAt=Instant.now();
    }

    public void complete(String status, int rawEventCount, int semanticActionCount, String irJson, String errorText) {
        this.status=status; this.rawEventCount=rawEventCount; this.semanticActionCount=semanticActionCount;
        this.irJson=irJson; this.errorText=errorText; this.updatedAt=Instant.now();
    }

    public UUID getId(){return id;} public UUID getWorkspaceId(){return workspaceId;} public UUID getApplicationId(){return applicationId;}
    public UUID getEnvironmentId(){return environmentId;} public String getWorkerSessionId(){return workerSessionId;} public String getScenarioName(){return scenarioName;}
    public String getModuleName(){return moduleName;} public String getFeatureName(){return featureName;} public String getStatus(){return status;}
    public String getStartUrl(){return startUrl;} public String getBrowser(){return browser;} public int getRawEventCount(){return rawEventCount;}
    public int getSemanticActionCount(){return semanticActionCount;} public String getIrJson(){return irJson;} public String getErrorText(){return errorText;}
    public UUID getCreatedBy(){return createdBy;} public Instant getCreatedAt(){return createdAt;} public Instant getUpdatedAt(){return updatedAt;}
}
