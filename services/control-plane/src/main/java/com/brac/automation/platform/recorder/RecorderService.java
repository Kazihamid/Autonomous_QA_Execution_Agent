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
import tools.jackson.databind.node.ObjectNode;

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
        // 1) Idempotent: the same recording session never produces a second scenario/version.
        var already = versions.findFirstBySourceRecordingSessionId(session.getId());
        if (already.isPresent()) {
            return scenarios.findByIdAndWorkspaceIdAndApplicationId(already.get().getScenarioId(), workspaceId, applicationId)
                .map(this::scenarioResponse)
                .orElseThrow(() -> new ResourceNotFoundException("Scenario not found."));
        }
        List<TestScenarioEntity> existing = scenarios.findByWorkspaceIdAndApplicationIdOrderByExecutionOrderAscModuleNameAscFeatureNameAscNameAsc(workspaceId, applicationId);
        String key = scenarioKey(session.getModuleName(), session.getFeatureName(), session.getScenarioName());
        TestScenarioEntity match = existing.stream().filter(x -> scenarioKey(x.getModuleName(), x.getFeatureName(), x.getName()).equals(key)).findFirst().orElse(null);
        TestScenarioEntity scenario;
        int versionNo;
        if (match != null) {
            // 2) Same module/feature/name (case-insensitive): record as a new VERSION of that scenario, not a duplicate.
            scenario = match;
            versionNo = scenario.bumpVersion();
            scenarios.save(scenario);
        } else {
            // 3) New scenario, appended at the end of the execution order.
            int next = existing.stream().map(TestScenarioEntity::getExecutionOrder).filter(java.util.Objects::nonNull).max(Integer::compare).orElse(0) + 1;
            scenario = scenarios.save(new TestScenarioEntity(workspaceId, applicationId, session.getModuleName(), session.getFeatureName(), session.getScenarioName(), next, currentUser.currentUser().getId()));
            versionNo = 1;
        }
        versions.save(new ScenarioVersionEntity(scenario.getId(), versionNo, session.getId(), session.getIrJson(), currentUser.currentUser().getId()));
        audit.success(workspaceId, "SCENARIO_VERSION_CREATED", "TEST_SCENARIO", scenario.getId(), Map.of("version", versionNo, "recordingSessionId", session.getId()));
        return scenarioResponse(scenario);
    }

    @Transactional(readOnly=true)
    public List<RecorderDtos.ScenarioResponse> listScenarios(UUID workspaceId, UUID applicationId) {
        guard.requireRead(workspaceId); applications.entity(workspaceId, applicationId);
        return scenarios.findByWorkspaceIdAndApplicationIdOrderByExecutionOrderAscModuleNameAscFeatureNameAscNameAsc(workspaceId, applicationId).stream().map(this::scenarioResponse).toList();
    }

    /** Persists the explicit execution order. Listed scenarios come first in the given order; any others keep their relative order after them. */
    @Transactional
    public List<RecorderDtos.ScenarioResponse> reorderScenarios(UUID workspaceId, UUID applicationId, RecorderDtos.ReorderRequest request) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        List<TestScenarioEntity> all = scenarios.findByWorkspaceIdAndApplicationIdOrderByExecutionOrderAscModuleNameAscFeatureNameAscNameAsc(workspaceId, applicationId);
        java.util.Map<UUID, TestScenarioEntity> byId = new java.util.LinkedHashMap<>();
        all.forEach(x -> byId.put(x.getId(), x));
        java.util.LinkedHashSet<UUID> ordered = new java.util.LinkedHashSet<>(request.scenarioIds());
        for (UUID id : ordered) if (!byId.containsKey(id)) throw new ResourceNotFoundException("Scenario not found: " + id);
        java.util.List<TestScenarioEntity> finalOrder = new java.util.ArrayList<>();
        ordered.forEach(id -> finalOrder.add(byId.get(id)));
        all.stream().filter(x -> !ordered.contains(x.getId())).forEach(finalOrder::add);
        for (int i = 0; i < finalOrder.size(); i++) finalOrder.get(i).setExecutionOrder(i + 1);
        scenarios.saveAll(finalOrder);
        audit.success(workspaceId, "SCENARIO_ORDER_UPDATED", "APPLICATION", applicationId, Map.of("count", finalOrder.size()));
        return finalOrder.stream().map(this::scenarioResponse).toList();
    }

    private static String scenarioKey(String module, String feature, String name) {
        return norm(module) + "|" + norm(feature) + "|" + norm(name);
    }
    private static String norm(String v) { return v == null ? "" : v.trim().replaceAll("\\s+", " ").toLowerCase(java.util.Locale.ROOT); }

    private static final java.util.regex.Pattern SECRET_NAME = java.util.regex.Pattern.compile("^[A-Za-z_][A-Za-z0-9_]{0,63}$");

    /**
     * Creates a NEW scenario from an existing one with edited parameter defaults and/or renamed secret references.
     * Only values are edited; the step structure is copied unchanged. Passwords are never stored: a secret is a
     * reference name whose value lives in the runner's environment (.env.runtime).
     */
    @Transactional
    public RecorderDtos.ScenarioResponse cloneScenario(UUID workspaceId, UUID applicationId, UUID scenarioId, RecorderDtos.CloneScenarioRequest request) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        TestScenarioEntity source = scenarios.findByIdAndWorkspaceIdAndApplicationId(scenarioId, workspaceId, applicationId)
            .orElseThrow(() -> new ResourceNotFoundException("Scenario not found."));
        ScenarioVersionEntity version = versions.findFirstByScenarioIdOrderByVersionNoDesc(scenarioId)
            .orElseThrow(() -> new ResourceNotFoundException("Scenario version not found."));
        JsonNode parsed = parse(version.getAutomationIr());
        if (parsed == null || !parsed.isObject()) throw new ConflictException("The source scenario does not contain valid Automation IR.");
        ObjectNode ir = ((ObjectNode) parsed).deepCopy();

        String name = request.name().trim();
        String module = clean(request.moduleName()) != null ? clean(request.moduleName()) : source.getModuleName();
        String feature = clean(request.featureName()) != null ? clean(request.featureName()) : source.getFeatureName();
        List<TestScenarioEntity> existing = scenarios.findByWorkspaceIdAndApplicationIdOrderByExecutionOrderAscModuleNameAscFeatureNameAscNameAsc(workspaceId, applicationId);
        String key = scenarioKey(module, feature, name);
        if (existing.stream().anyMatch(x -> scenarioKey(x.getModuleName(), x.getFeatureName(), x.getName()).equals(key))) {
            throw new ConflictException("A scenario with this module, feature and name already exists. Choose a different name.");
        }

        if (request.parameters() != null) {
            JsonNode params = ir.path("parameters");
            for (var e : request.parameters().entrySet()) {
                JsonNode p = params.get(e.getKey());
                if (p == null || !p.isObject()) throw new IllegalArgumentException("Unknown parameter: " + e.getKey());
                if (e.getValue() == null || e.getValue().length() > 2000) throw new IllegalArgumentException("Invalid value for parameter: " + e.getKey());
                ((ObjectNode) p).put("default", e.getValue());
            }
        }
        if (request.secretReferences() != null && !request.secretReferences().isEmpty()) {
            java.util.Set<String> known = new java.util.HashSet<>();
            for (JsonNode step : ir.path("steps")) {
                JsonNode v = step.get("value");
                if (v != null && v.isObject() && "secret".equals(v.path("source").asText())) known.add(v.path("reference").asText());
            }
            for (var e : request.secretReferences().entrySet()) {
                if (!known.contains(e.getKey())) throw new IllegalArgumentException("Unknown secret reference: " + e.getKey());
                if (e.getValue() == null || !SECRET_NAME.matcher(e.getValue()).matches()) {
                    throw new IllegalArgumentException("Secret names must be letters, digits and underscores (for example SECRET_PASSWORD_ENV27).");
                }
            }
            for (JsonNode step : ir.path("steps")) {
                JsonNode v = step.get("value");
                if (v != null && v.isObject() && "secret".equals(v.path("source").asText())) {
                    String replacement = request.secretReferences().get(v.path("reference").asText());
                    if (replacement != null) ((ObjectNode) v).put("reference", replacement);
                }
            }
        }

        int next = existing.stream().map(TestScenarioEntity::getExecutionOrder).filter(java.util.Objects::nonNull).max(Integer::compare).orElse(0) + 1;
        TestScenarioEntity created = scenarios.save(new TestScenarioEntity(workspaceId, applicationId, module, feature, name, next, currentUser.currentUser().getId()));
        ObjectNode sc = ir.get("scenario") != null && ir.get("scenario").isObject() ? (ObjectNode) ir.get("scenario") : ir.putObject("scenario");
        sc.put("id", created.getId().toString());
        sc.put("name", name);
        ObjectNode meta = ir.get("metadata") != null && ir.get("metadata").isObject() ? (ObjectNode) ir.get("metadata") : ir.putObject("metadata");
        meta.put("source", "clone");
        ObjectNode from = meta.putObject("clonedFrom");
        from.put("scenarioId", source.getId().toString());
        from.put("scenarioName", source.getName());
        from.put("version", version.getVersionNo());
        versions.save(new ScenarioVersionEntity(created.getId(), 1, null, mapper.writeValueAsString(ir), currentUser.currentUser().getId()));
        audit.success(workspaceId, "SCENARIO_CLONED", "TEST_SCENARIO", created.getId(), Map.of("sourceScenarioId", source.getId().toString(), "name", name));
        return scenarioResponse(created);
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
        return new RecorderDtos.ScenarioResponse(s.getId(), s.getWorkspaceId(), s.getApplicationId(), s.getModuleName(), s.getFeatureName(), s.getName(), s.getStatus(), s.getCurrentVersion(), s.getExecutionOrder(), s.getCreatedAt());
    }

    private JsonNode parse(String json) {
        if (json == null || json.isBlank()) return null;
        try { return mapper.readTree(json); }
        catch (RuntimeException ex) { return null; }
    }
    private String clean(String value) { return value == null || value.isBlank() ? null : value.trim(); }
}
