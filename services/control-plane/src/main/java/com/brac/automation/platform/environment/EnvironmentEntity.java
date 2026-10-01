package com.brac.automation.platform.environment;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema="core", name="environment")
public class EnvironmentEntity {
    @Id private UUID id;
    @Column(name="application_id", nullable=false) private UUID applicationId;
    @Column(nullable=false) private String name;
    @Column(name="base_url", nullable=false) private String baseUrl;
    @Column(name="default_browser", nullable=false) private String defaultBrowser;
    @Column(name="headless_default", nullable=false) private boolean headlessDefault;
    @Column(name="allow_recording", nullable=false) private boolean allowRecording;
    @Column(name="allow_execution", nullable=false) private boolean allowExecution;
    @Column(name="validation_status", nullable=false) private String validationStatus;
    @Column(nullable=false) private String status;
    @Column(name="created_by", nullable=false) private UUID createdBy;
    @Column(name="created_at", nullable=false) private Instant createdAt;
    @Column(name="updated_at", nullable=false) private Instant updatedAt;
    protected EnvironmentEntity() {}
    public EnvironmentEntity(UUID applicationId,String name,String baseUrl,String defaultBrowser,boolean headlessDefault,boolean allowRecording,boolean allowExecution,String validationStatus,UUID createdBy){
        this.id=UUID.randomUUID();this.applicationId=applicationId;this.name=name;this.baseUrl=baseUrl;this.defaultBrowser=defaultBrowser;this.headlessDefault=headlessDefault;
        this.allowRecording=allowRecording;this.allowExecution=allowExecution;this.validationStatus=validationStatus;this.status="ACTIVE";this.createdBy=createdBy;this.createdAt=Instant.now();this.updatedAt=this.createdAt;
    }
    public void update(String name,String baseUrl,String defaultBrowser,boolean headlessDefault,boolean allowRecording,boolean allowExecution,String validationStatus,String status){
        this.name=name;this.baseUrl=baseUrl;this.defaultBrowser=defaultBrowser;this.headlessDefault=headlessDefault;this.allowRecording=allowRecording;this.allowExecution=allowExecution;this.validationStatus=validationStatus;this.status=status;this.updatedAt=Instant.now();
    }
    public UUID getId(){return id;} public UUID getApplicationId(){return applicationId;} public String getName(){return name;} public String getBaseUrl(){return baseUrl;}
    public String getDefaultBrowser(){return defaultBrowser;} public boolean isHeadlessDefault(){return headlessDefault;} public boolean isAllowRecording(){return allowRecording;}
    public boolean isAllowExecution(){return allowExecution;} public String getValidationStatus(){return validationStatus;} public String getStatus(){return status;} public Instant getCreatedAt(){return createdAt;}
}
