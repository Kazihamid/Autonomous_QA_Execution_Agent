package com.brac.automation.platform.application;

import com.brac.automation.platform.audit.AuditService;
import com.brac.automation.platform.common.ConflictException;
import com.brac.automation.platform.common.ResourceNotFoundException;
import com.brac.automation.platform.environment.EnvironmentRepository;
import com.brac.automation.platform.recorder.RecordingSessionRepository;
import com.brac.automation.platform.recorder.TestScenarioRepository;
import com.brac.automation.platform.security.CurrentUserService;
import com.brac.automation.platform.workspace.WorkspaceAccessGuard;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ApplicationService {
    private final ApplicationRepository repository;
    private final WorkspaceAccessGuard guard;
    private final CurrentUserService currentUser;
    private final AuditService audit;
    private final EnvironmentRepository environments;
    private final TestScenarioRepository scenarios;
    private final RecordingSessionRepository recordings;
    public ApplicationService(ApplicationRepository repository, WorkspaceAccessGuard guard, CurrentUserService currentUser, AuditService audit,
            EnvironmentRepository environments, TestScenarioRepository scenarios, RecordingSessionRepository recordings) {
        this.repository=repository; this.guard=guard; this.currentUser=currentUser; this.audit=audit;
        this.environments=environments; this.scenarios=scenarios; this.recordings=recordings;
    }

    @Transactional(readOnly=true)
    public List<ApplicationDtos.Response> list(UUID workspaceId) {
        guard.requireRead(workspaceId);
        return repository.findByWorkspaceIdOrderByNameAsc(workspaceId).stream().map(this::response).toList();
    }

    @Transactional(readOnly=true)
    public ApplicationDtos.Response get(UUID workspaceId, UUID applicationId) {
        guard.requireRead(workspaceId); return response(entity(workspaceId, applicationId));
    }

    @Transactional
    public ApplicationDtos.Response create(UUID workspaceId, ApplicationDtos.CreateRequest request) {
        guard.requireWrite(workspaceId);
        String name=request.name().trim();
        if(repository.existsByWorkspaceIdAndNameIgnoreCase(workspaceId,name)) throw new ConflictException("Application name already exists in workspace.");
        ApplicationEntity app=repository.save(new ApplicationEntity(workspaceId,name,clean(request.description()),currentUser.currentUser().getId()));
        audit.success(workspaceId,"APPLICATION_CREATED","APPLICATION",app.getId(),Map.of("name",name));
        return response(app);
    }

    @Transactional
    public void delete(UUID workspaceId, UUID applicationId) {
        guard.requireWrite(workspaceId);
        ApplicationEntity app=entity(workspaceId,applicationId);
        long envCount=environments.countByApplicationId(applicationId);
        long scenarioCount=scenarios.countByApplicationId(applicationId);
        long recordingCount=recordings.countByApplicationId(applicationId);
        if(envCount>0 || scenarioCount>0 || recordingCount>0) {
            throw new ConflictException("Application cannot be deleted because dependent environments, scenarios, or recording history exist. Archive the application instead.");
        }
        repository.delete(app);
        audit.success(workspaceId,"APPLICATION_DELETED","APPLICATION",applicationId,Map.of("name",app.getName()));
    }

    @Transactional
    public ApplicationDtos.Response update(UUID workspaceId, UUID applicationId, ApplicationDtos.UpdateRequest request) {
        guard.requireWrite(workspaceId);
        ApplicationEntity app=entity(workspaceId,applicationId);
        String name=request.name().trim();
        if(repository.existsByWorkspaceIdAndNameIgnoreCaseAndIdNot(workspaceId,name,applicationId)) throw new ConflictException("Application name already exists in workspace.");
        app.update(name,clean(request.description()),request.status());
        repository.save(app);
        audit.success(workspaceId,"APPLICATION_UPDATED","APPLICATION",app.getId(),Map.of("status",app.getStatus()));
        return response(app);
    }

    public ApplicationEntity entity(UUID workspaceId, UUID applicationId) {
        return repository.findByIdAndWorkspaceId(applicationId,workspaceId).orElseThrow(() -> new ResourceNotFoundException("Application not found."));
    }
    private ApplicationDtos.Response response(ApplicationEntity a){return new ApplicationDtos.Response(a.getId(),a.getWorkspaceId(),a.getName(),a.getDescription(),a.getStatus(),a.getCreatedAt());}
    private String clean(String v){return v==null||v.isBlank()?null:v.trim();}
}
