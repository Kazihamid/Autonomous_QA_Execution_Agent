package com.brac.automation.platform.environment;

import com.brac.automation.platform.application.ApplicationEntity;
import com.brac.automation.platform.application.ApplicationService;
import com.brac.automation.platform.audit.AuditService;
import com.brac.automation.platform.common.ConflictException;
import com.brac.automation.platform.common.ResourceNotFoundException;
import com.brac.automation.platform.common.PolicyViolationException;
import com.brac.automation.platform.security.CurrentUserService;
import com.brac.automation.platform.recorder.RecordingSessionRepository;
import com.brac.automation.platform.workspace.WorkspaceAccessGuard;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class EnvironmentService {
    private final EnvironmentRepository repository;
    private final ApplicationService applications;
    private final WorkspaceAccessGuard guard;
    private final EnvironmentTargetValidator targetValidator;
    private final CurrentUserService currentUser;
    private final AuditService audit;
    private final RecordingSessionRepository recordingSessions;
    public EnvironmentService(EnvironmentRepository repository,ApplicationService applications,WorkspaceAccessGuard guard,EnvironmentTargetValidator targetValidator,CurrentUserService currentUser,AuditService audit,RecordingSessionRepository recordingSessions){
        this.repository=repository;this.applications=applications;this.guard=guard;this.targetValidator=targetValidator;this.currentUser=currentUser;this.audit=audit;this.recordingSessions=recordingSessions;
    }

    @Transactional(readOnly=true)
    public List<EnvironmentDtos.Response> list(UUID workspaceId,UUID applicationId){guard.requireRead(workspaceId);applications.entity(workspaceId,applicationId);return repository.findByApplicationIdOrderByNameAsc(applicationId).stream().map(this::response).toList();}

    @Transactional
    public EnvironmentDtos.Response create(UUID workspaceId,UUID applicationId,EnvironmentDtos.CreateRequest request){
        guard.requireWrite(workspaceId); ApplicationEntity app=applications.entity(workspaceId,applicationId);
        if(repository.existsByApplicationIdAndNameIgnoreCase(applicationId,request.name().trim())) throw new ConflictException("Environment name already exists for application.");
        TargetValidationResult result=targetValidator.validate(request.baseUrl().trim());
        String validationStatus=result.dnsResolved()?"VALIDATED":"UNVERIFIED";
        EnvironmentEntity env=repository.save(new EnvironmentEntity(app.getId(),request.name().trim(),request.baseUrl().trim(),request.defaultBrowser(),request.headlessDefault(),request.allowRecording(),request.allowExecution(),validationStatus,currentUser.currentUser().getId()));
        audit.success(workspaceId,"ENVIRONMENT_CREATED","ENVIRONMENT",env.getId(),Map.of("validationStatus",validationStatus));
        return response(env);
    }

    @Transactional
    public EnvironmentDtos.Response update(UUID workspaceId,UUID applicationId,UUID environmentId,EnvironmentDtos.UpdateRequest request){
        guard.requireWrite(workspaceId);applications.entity(workspaceId,applicationId);
        EnvironmentEntity env=repository.findByIdAndApplicationId(environmentId,applicationId).orElseThrow(() -> new ResourceNotFoundException("Environment not found."));
        if(repository.existsByApplicationIdAndNameIgnoreCaseAndIdNot(applicationId,request.name().trim(),environmentId)) throw new ConflictException("Environment name already exists for application.");
        TargetValidationResult result=targetValidator.validate(request.baseUrl().trim());
        String validationStatus=result.dnsResolved()?"VALIDATED":"UNVERIFIED";
        env.update(request.name().trim(),request.baseUrl().trim(),request.defaultBrowser(),request.headlessDefault(),request.allowRecording(),request.allowExecution(),validationStatus,request.status());
        repository.save(env); audit.success(workspaceId,"ENVIRONMENT_UPDATED","ENVIRONMENT",env.getId(),Map.of("validationStatus",validationStatus,"status",request.status()));
        return response(env);
    }

    @Transactional
    public void delete(UUID workspaceId,UUID applicationId,UUID environmentId){
        guard.requireWrite(workspaceId);applications.entity(workspaceId,applicationId);
        EnvironmentEntity env=repository.findByIdAndApplicationId(environmentId,applicationId).orElseThrow(() -> new ResourceNotFoundException("Environment not found."));
        long recordings=recordingSessions.countByEnvironmentId(environmentId);
        if(recordings>0) throw new ConflictException("Environment cannot be deleted because recording history exists. Disable the environment instead.");
        repository.delete(env);
        audit.success(workspaceId,"ENVIRONMENT_DELETED","ENVIRONMENT",environmentId,Map.of("name",env.getName()));
    }

    @Transactional(readOnly=true)
    public EnvironmentDtos.TargetValidationResponse validateTarget(UUID workspaceId,UUID applicationId,String url){
        guard.requireRead(workspaceId);applications.entity(workspaceId,applicationId);TargetValidationResult r=targetValidator.validate(url);
        return new EnvironmentDtos.TargetValidationResponse(r.valid(),r.dnsResolved(),r.resolvedAddresses(),r.warnings());
    }

    @Transactional(readOnly=true)
    public EnvironmentEntity requireRecordable(UUID workspaceId,UUID applicationId,UUID environmentId){
        guard.requireWrite(workspaceId);applications.entity(workspaceId,applicationId);
        EnvironmentEntity env=repository.findByIdAndApplicationId(environmentId,applicationId).orElseThrow(() -> new ResourceNotFoundException("Environment not found."));
        if(!"ACTIVE".equals(env.getStatus())) throw new PolicyViolationException("Environment is not ACTIVE.");
        if(!env.isAllowRecording()) throw new PolicyViolationException("Recording is disabled for this environment.");
        targetValidator.validate(env.getBaseUrl());
        return env;
    }

    private EnvironmentDtos.Response response(EnvironmentEntity e){return new EnvironmentDtos.Response(e.getId(),e.getApplicationId(),e.getName(),e.getBaseUrl(),e.getDefaultBrowser(),e.isHeadlessDefault(),e.isAllowRecording(),e.isAllowExecution(),e.getValidationStatus(),e.getStatus(),e.getCreatedAt());}
}
