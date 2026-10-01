package com.brac.automation.platform.codegen;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema="core", name="automation_implementation")
public class AutomationImplementationEntity {
    @Id private UUID id;
    @Column(name="workspace_id", nullable=false) private UUID workspaceId;
    @Column(name="application_id", nullable=false) private UUID applicationId;
    @Column(name="scenario_id", nullable=false) private UUID scenarioId;
    @Column(name="scenario_version_id", nullable=false) private UUID scenarioVersionId;
    @Column(name="implementation_version", nullable=false) private int implementationVersion;
    @Column(name="target_profile", nullable=false) private String targetProfile;
    @Column(name="generator_version", nullable=false) private String generatorVersion;
    @Column(nullable=false) private String status;
    @Column(name="ir_canonical_hash", nullable=false) private String irCanonicalHash;
    @Column(name="source_hash", nullable=false) private String sourceHash;
    @Column(name="files_json", nullable=false, columnDefinition="text") private String filesJson;
    @Column(name="source_map_json", nullable=false, columnDefinition="text") private String sourceMapJson;
    @Column(name="validation_json", nullable=false, columnDefinition="text") private String validationJson;
    @Column(name="created_by", nullable=false) private UUID createdBy;
    @Column(name="created_at", nullable=false) private Instant createdAt;
    protected AutomationImplementationEntity() {}
    public AutomationImplementationEntity(UUID workspaceId, UUID applicationId, UUID scenarioId, UUID scenarioVersionId, int implementationVersion,
        String targetProfile, String generatorVersion, String status, String irCanonicalHash, String sourceHash, String filesJson, String sourceMapJson, String validationJson, UUID createdBy) {
        this.id=UUID.randomUUID(); this.workspaceId=workspaceId; this.applicationId=applicationId; this.scenarioId=scenarioId; this.scenarioVersionId=scenarioVersionId;
        this.implementationVersion=implementationVersion; this.targetProfile=targetProfile; this.generatorVersion=generatorVersion; this.status=status; this.irCanonicalHash=irCanonicalHash;
        this.sourceHash=sourceHash; this.filesJson=filesJson; this.sourceMapJson=sourceMapJson; this.validationJson=validationJson; this.createdBy=createdBy; this.createdAt=Instant.now();
    }
    public UUID getId(){return id;} public UUID getWorkspaceId(){return workspaceId;} public UUID getApplicationId(){return applicationId;} public UUID getScenarioId(){return scenarioId;}
    public UUID getScenarioVersionId(){return scenarioVersionId;} public int getImplementationVersion(){return implementationVersion;} public String getTargetProfile(){return targetProfile;}
    public String getGeneratorVersion(){return generatorVersion;} public String getStatus(){return status;} public String getIrCanonicalHash(){return irCanonicalHash;} public String getSourceHash(){return sourceHash;}
    public String getFilesJson(){return filesJson;} public String getSourceMapJson(){return sourceMapJson;} public String getValidationJson(){return validationJson;} public Instant getCreatedAt(){return createdAt;}
}
