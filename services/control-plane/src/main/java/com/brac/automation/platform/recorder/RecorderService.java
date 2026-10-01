package com.brac.automation.platform.recorder;

import com.brac.automation.platform.application.ApplicationService;
import com.brac.automation.platform.audit.AuditService;
import com.brac.automation.platform.codegen.AutomationImplementationRepository;
import com.brac.automation.platform.common.ConflictException;
import com.brac.automation.platform.common.ResourceNotFoundException;
import com.brac.automation.platform.environment.EnvironmentEntity;
import com.brac.automation.platform.environment.EnvironmentService;
import com.brac.automation.platform.security.CurrentUserService;
import com.brac.automation.platform.workspace.WorkspaceAccessGuard;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Service
public class RecorderService {
    private final RecordingSessionRepository sessions;
    private final TestScenarioRepository scenarios;
    private final ScenarioVersionRepository versions;
    private final ApplicationService applications;
    private final EnvironmentService environments;
    private final WorkspaceAccessGuard guard;
    private final CurrentUserService currentUser;
    private final AuditService audit;
    private final RecorderWorkerClient worker;
    private final ObjectMapper mapper;
    private final AutomationImplementationRepository implementations;

    public RecorderService(RecordingSessionRepository sessions, TestScenarioRepository scenarios, ScenarioVersionRepository versions,
                           ApplicationService applications, EnvironmentService environments, WorkspaceAccessGuard guard,
                           CurrentUserService currentUser, AuditService audit, RecorderWorkerClient worker, ObjectMapper mapper,
                           AutomationImplementationRepository implementations) {
        this.sessions=sessions; this.scenarios=scenarios; this.versions=versions; this.applications=applications; this.environments=environments;
        this.guard=guard; this.currentUser=currentUser; this.audit=audit; this.worker=worker; this.mapper=mapper; this.implementations=implementations;
    }

    @Transactional
    public RecorderDtos.SessionResponse create(UUID workspaceId, UUID applicationId, UUID environmentId, RecorderDtos.CreateSessionRequest request) {
        guard.requireWrite(workspaceId);
        applications.entity(workspaceId, applicationId);
        EnvironmentEntity env = environments.requireRecordable(workspaceId, applicationId, environmentId);
        String scenarioName = request.scenarioName().trim();
        RecorderWorkerClient.WorkerSession ws = worker.create(env.getBaseUrl(), env.getDefaultBrowser(), scenarioName);
        RecordingSessionEntity entity = sessions.save(new RecordingSessionEntity(
            workspaceId, applicationId, environmentId, ws.sessionId(), scenarioName, clean(request.moduleName()), clean(request.featureName()),
            ws.status(), env.getBaseUrl(), env.getDefaultBrowser(), currentUser.currentUser().getId()));
        entity.updateWorkerStatus(ws.status(), ws.error());
        sessions.save(entity);
        audit.success(workspaceId, "RECORDER_SESSION_CREATED", "RECORDING_SESSION", entity.getId(), Map.of("environmentId", environmentId, "status", ws.status()));
        return response(entity);
    }

    @Transactional(readOnly=true)
    public List<RecorderDtos.SessionResponse> listSessions(UUID workspaceId, UUID applicationId) {
        guard.requireRead(workspaceId); applications.entity(workspaceId, applicationId);
        return sessions.findByWorkspaceIdAndApplicationIdOrderByCreatedAtDesc(workspaceId, applicationId).stream().map(this::response).toList();
    }

    @Transactional(readOnly=true)
    public RecorderDtos.SessionResponse getSession(UUID workspaceId, UUID applicationId, UUID sessionId) {
        guard.requireRead(workspaceId); applications.entity(workspaceId, applicationId); return response(entity(workspaceId, applicationId, sessionId));
    }

    @Transactional
    public RecorderDtos.SessionResponse command(UUID workspaceId, UUID applicationId, UUID sessionId, String command) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        RecordingSessionEntity entity = entity(workspaceId, applicationId, sessionId);
        RecorderWorkerClient.WorkerSession ws = worker.command(entity.getWorkerSessionId(), command);
        entity.updateWorkerStatus(ws.status(), ws.error()); sessions.save(entity);
        audit.success(workspaceId, "RECORDER_SESSION_" + command.toUpperCase(), "RECORDING_SESSION", entity.getId(), Map.of("status", ws.status()));
        return response(entity);
    }

    public void addAssertion(UUID workspaceId, UUID applicationId, UUID sessionId, RecorderDtos.AssertionRequest request) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        RecordingSessionEntity entity = entity(workspaceId, applicationId, sessionId);
        worker.addAssertion(entity.getWorkerSessionId(), request.selector().trim(), request.assertionType(), request.expected());
        audit.success(workspaceId, "RECORDER_ASSERTION_ADDED", "RECORDING_SESSION", entity.getId(), Map.of("type", request.assertionType()));
    }

    public void addCheckpoint(UUID workspaceId, UUID applicationId, UUID sessionId, RecorderDtos.CheckpointRequest request) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        RecordingSessionEntity entity = entity(workspaceId, applicationId, sessionId);
        worker.addCheckpoint(entity.getWorkerSessionId(), request.description().trim());
        audit.success(workspaceId, "RECORDER_CHECKPOINT_ADDED", "RECORDING_SESSION", entity.getId(), Map.of());
    }

    @Transactional
    public RecorderDtos.SessionResponse finish(UUID workspaceId, UUID applicationId, UUID sessionId) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        RecordingSessionEntity entity = entity(workspaceId, applicationId, sessionId);
        RecorderWorkerClient.FinishResponse result = worker.finish(entity.getWorkerSessionId());
        String irJson = result.ir() == null ? null : result.ir().toString();
        String error = result.errors() == null || result.errors().isEmpty() ? result.session().error() : String.join("; ", result.errors());
        entity.complete(result.session().status(), result.rawEventCount(), result.semanticActionCount(), irJson, error);
        sessions.save(entity);
        audit.success(workspaceId, "RECORDER_SESSION_FINISHED", "RECORDING_SESSION", entity.getId(), Map.of(
            "status", entity.getStatus(), "rawEvents", entity.getRawEventCount(), "semanticActions", entity.getSemanticActionCount()));
        return response(entity);
    }

    @Transactional
    public RecorderDtos.ScenarioResponse saveScenario(UUID workspaceId, UUID applicationId, UUID sessionId) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        RecordingSessionEntity session = entity(workspaceId, applicationId, sessionId);
        if (!"COMPLETED".equals(session.getStatus()) || session.getIrJson() == null || session.getIrJson().isBlank()) {
            throw new ConflictException("Only a COMPLETED recording session with valid Automation IR can be saved as a scenario.");
        }
        TestScenarioEntity scenario = scenarios.save(new TestScenarioEntity(workspaceId, applicationId, session.getModuleName(), session.getFeatureName(), session.getScenarioName(), currentUser.currentUser().getId()));
        versions.save(new ScenarioVersionEntity(scenario.getId(), 1, session.getId(), session.getIrJson(), currentUser.currentUser().getId()));
        audit.success(workspaceId, "SCENARIO_VERSION_CREATED", "TEST_SCENARIO", scenario.getId(), Map.of("version", 1, "recordingSessionId", session.getId()));
        return scenarioResponse(scenario);
    }

    @Transactional(readOnly=true)
    public List<RecorderDtos.ScenarioResponse> listScenarios(UUID workspaceId, UUID applicationId) {
        guard.requireRead(workspaceId); applications.entity(workspaceId, applicationId);
        return scenarios.findByWorkspaceIdAndApplicationIdOrderByModuleNameAscFeatureNameAscNameAsc(workspaceId, applicationId).stream().map(this::scenarioResponse).toList();
    }

    @Transactional
    public void deleteScenario(UUID workspaceId, UUID applicationId, UUID scenarioId) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        TestScenarioEntity scenario = scenarios.findByIdAndWorkspaceIdAndApplicationId(scenarioId, workspaceId, applicationId)
            .orElseThrow(() -> new ResourceNotFoundException("Scenario not found."));
        implementations.deleteByScenarioId(scenarioId);
        versions.deleteByScenarioId(scenarioId);
        scenarios.delete(scenario);
        audit.success(workspaceId, "SCENARIO_DELETED", "TEST_SCENARIO", scenarioId, Map.of("name", scenario.getName()));
    }

    @Transactional(readOnly=true)
    public RecorderDtos.ScenarioDetailResponse getScenario(UUID workspaceId, UUID applicationId, UUID scenarioId) {
        guard.requireRead(workspaceId); applications.entity(workspaceId, applicationId);
        TestScenarioEntity scenario = scenarios.findByIdAndWorkspaceIdAndApplicationId(scenarioId, workspaceId, applicationId)
            .orElseThrow(() -> new ResourceNotFoundException("Scenario not found."));
        ScenarioVersionEntity version = versions.findFirstByScenarioIdOrderByVersionNoDesc(scenarioId)
            .orElseThrow(() -> new ResourceNotFoundException("Scenario version not found."));
        return new RecorderDtos.ScenarioDetailResponse(scenarioResponse(scenario), version.getVersionNo(), version.getSourceRecordingSessionId(), parse(version.getAutomationIr()), version.getCreatedAt());
    }

    private RecordingSessionEntity entity(UUID workspaceId, UUID applicationId, UUID sessionId) {
        return sessions.findByIdAndWorkspaceIdAndApplicationId(sessionId, workspaceId, applicationId)
            .orElseThrow(() -> new ResourceNotFoundException("Recording session not found."));
    }

    private RecorderDtos.SessionResponse response(RecordingSessionEntity e) {
        return new RecorderDtos.SessionResponse(e.getId(), e.getWorkspaceId(), e.getApplicationId(), e.getEnvironmentId(), e.getWorkerSessionId(), e.getScenarioName(),
            e.getModuleName(), e.getFeatureName(), e.getStatus(), e.getStartUrl(), e.getBrowser(), e.getRawEventCount(), e.getSemanticActionCount(), e.getErrorText(),
            parse(e.getIrJson()), e.getCreatedAt(), e.getUpdatedAt());
    }

    private RecorderDtos.ScenarioResponse scenarioResponse(TestScenarioEntity s) {
        return new RecorderDtos.ScenarioResponse(s.getId(), s.getWorkspaceId(), s.getApplicationId(), s.getModuleName(), s.getFeatureName(), s.getName(), s.getStatus(), s.getCurrentVersion(), s.getCreatedAt());
    }

    private JsonNode parse(String json) {
        if (json == null || json.isBlank()) return null;
        try { return mapper.readTree(json); }
        catch (RuntimeException ex) { return null; }
    }
    private String clean(String value) { return value == null || value.isBlank() ? null : value.trim(); }
}
