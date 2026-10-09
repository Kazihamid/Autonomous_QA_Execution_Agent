package com.brac.automation.platform.recorder;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema="core", name="test_scenario")
// A deleted scenario stays in the table (status DELETED) so it can be restored; every normal query ignores it.
@org.hibernate.annotations.SQLRestriction("status <> 'DELETED'")
public class TestScenarioEntity {
    @Id private UUID id;
    @Column(name="workspace_id", nullable=false) private UUID workspaceId;
    @Column(name="application_id", nullable=false) private UUID applicationId;
    @Column(name="module_name") private String moduleName;
    @Column(name="feature_name") private String featureName;
    @Column(nullable=false) private String name;
    @Column(nullable=false) private String status;
    @Column(name="current_version", nullable=false) private int currentVersion;
    @Column(name="execution_order") private Integer executionOrder;
    @Column(name="created_by", nullable=false) private UUID createdBy;
    @Column(name="created_at", nullable=false) private Instant createdAt;
    @Column(name="updated_at", nullable=false) private Instant updatedAt;

    protected TestScenarioEntity() {}
    public TestScenarioEntity(UUID workspaceId, UUID applicationId, String moduleName, String featureName, String name, Integer executionOrder, UUID createdBy) {
        this.id=UUID.randomUUID(); this.workspaceId=workspaceId; this.applicationId=applicationId; this.moduleName=moduleName; this.featureName=featureName;
        this.name=name; this.executionOrder=executionOrder; this.status="ACTIVE"; this.currentVersion=1; this.createdBy=createdBy; this.createdAt=Instant.now(); this.updatedAt=this.createdAt;
    }
    public UUID getId(){return id;} public UUID getWorkspaceId(){return workspaceId;} public UUID getApplicationId(){return applicationId;}
    public String getModuleName(){return moduleName;} public String getFeatureName(){return featureName;} public String getName(){return name;}
    public String getStatus(){return status;} public int getCurrentVersion(){return currentVersion;} public Instant getCreatedAt(){return createdAt;}
    public Integer getExecutionOrder(){return executionOrder;}
    public void setExecutionOrder(Integer order){this.executionOrder=order; this.updatedAt=Instant.now();}
    public void rename(String moduleName,String featureName,String name){this.moduleName=moduleName; this.featureName=featureName; this.name=name; this.updatedAt=Instant.now();}
    public int bumpVersion(){this.currentVersion++; this.updatedAt=Instant.now(); return this.currentVersion;}
}
