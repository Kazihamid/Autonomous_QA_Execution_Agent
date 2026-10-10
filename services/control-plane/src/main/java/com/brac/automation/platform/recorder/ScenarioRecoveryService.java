package com.brac.automation.platform.recorder;

import com.brac.automation.platform.application.ApplicationService;
import com.brac.automation.platform.audit.AuditService;
import com.brac.automation.platform.common.ResourceNotFoundException;
import com.brac.automation.platform.security.CurrentUserService;
import com.brac.automation.platform.workspace.WorkspaceAccessGuard;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.Query;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Stream;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

/**
 * Rollback and recovery for scenarios: restore a deleted scenario, restore an older version of a scenario,
 * recover a scenario from a finished recording that was never saved (or whose scenario is gone), and
 * export / import a backup file. A backup file is also written automatically after every change when SCENARIO_BACKUP_DIR is set.
 */
@Service
public class ScenarioRecoveryService {
    private static final Logger log = LoggerFactory.getLogger(ScenarioRecoveryService.class);
    private static final int KEEP_SNAPSHOTS = 200;

    @PersistenceContext
    private EntityManager em;

    private final TestScenarioRepository scenarios;
    private final ScenarioVersionRepository versions;
    private final ApplicationService applications;
    private final WorkspaceAccessGuard guard;
    private final CurrentUserService currentUser;
    private final AuditService audit;
    private final ObjectMapper mapper;

    @Value("${SCENARIO_BACKUP_DIR:}")
    private String backupDir;

    public ScenarioRecoveryService(TestScenarioRepository scenarios, ScenarioVersionRepository versions, ApplicationService applications,
                                   WorkspaceAccessGuard guard, CurrentUserService currentUser, AuditService audit, ObjectMapper mapper) {
        this.scenarios = scenarios; this.versions = versions; this.applications = applications;
        this.guard = guard; this.currentUser = currentUser; this.audit = audit; this.mapper = mapper;
    }

    // ---- small helpers -------------------------------------------------------------------------------------------

    private static UUID uuid(Object o) { return o == null ? null : UUID.fromString(String.valueOf(o)); }
    private static String text(Object o) { return o == null ? null : String.valueOf(o); }
    private static int num(Object o) { return o == null ? 0 : ((Number) o).intValue(); }
    private static String norm(String v) { return v == null ? "" : v.trim().toLowerCase(Locale.ROOT); }
    private static String blank(String v) { return v == null ? "" : v; }

    private static String time(Object o) {
        if (o == null) return null;
        if (o instanceof Instant i) return i.toString();
        if (o instanceof java.time.OffsetDateTime t) return t.toInstant().toString();
        if (o instanceof java.sql.Timestamp t) return t.toInstant().toString();
        if (o instanceof LocalDateTime t) return t.toInstant(ZoneOffset.UTC).toString();
        return String.valueOf(o);
    }

    private static String str(JsonNode n) {
        if (n == null || n.isNull() || n.isMissingNode()) return null;
        String v = n.asText();
        return v == null || v.isBlank() ? null : v;
    }

    @SuppressWarnings("unchecked")
    private static List<Object[]> rows(Query q) { return (List<Object[]>) q.getResultList(); }

    private RecorderDtos.ScenarioResponse response(TestScenarioEntity s) {
        return new RecorderDtos.ScenarioResponse(s.getId(), s.getWorkspaceId(), s.getApplicationId(), s.getModuleName(), s.getFeatureName(),
            s.getName(), s.getStatus(), s.getCurrentVersion(), s.getExecutionOrder(), s.getCreatedAt());
    }

    private boolean taken(UUID workspaceId, UUID applicationId, String module, String feature, String name) {
        Query q = em.createNativeQuery("select count(*) from core.test_scenario where workspace_id = :w and application_id = :a and status <> 'DELETED' "
            + "and lower(btrim(coalesce(module_name, ''))) = :m and lower(btrim(coalesce(feature_name, ''))) = :f and lower(btrim(name)) = :n");
        q.setParameter("w", workspaceId); q.setParameter("a", applicationId);
        q.setParameter("m", norm(module)); q.setParameter("f", norm(feature)); q.setParameter("n", norm(name));
        return ((Number) q.getSingleResult()).longValue() > 0;
    }

    /** The name itself when free, otherwise "name (restored)", "name (restored 2)" ... so nothing is overwritten. */
    private String freeName(UUID workspaceId, UUID applicationId, String module, String feature, String name, String label) {
        String candidate = name;
        for (int n = 0; n < 50 && taken(workspaceId, applicationId, module, feature, candidate); n++) {
            String suffix = " (" + label + (n == 0 ? "" : " " + (n + 1)) + ")";
            String base = name.length() + suffix.length() > 200 ? name.substring(0, 200 - suffix.length()) : name;
            candidate = base + suffix;
        }
        return candidate;
    }

    // ---- recently deleted ----------------------------------------------------------------------------------------

    @Transactional(readOnly = true)
    public List<RecoveryDtos.DeletedScenario> listDeleted(UUID workspaceId, UUID applicationId) {
        guard.requireRead(workspaceId); applications.entity(workspaceId, applicationId);
        Query q = em.createNativeQuery("select id, module_name, feature_name, name, current_version, deleted_at from core.test_scenario "
            + "where workspace_id = :w and application_id = :a and status = 'DELETED' order by deleted_at desc nulls last, name");
        q.setParameter("w", workspaceId); q.setParameter("a", applicationId);
        List<RecoveryDtos.DeletedScenario> out = new ArrayList<>();
        for (Object[] r : rows(q)) out.add(new RecoveryDtos.DeletedScenario(uuid(r[0]), text(r[1]), text(r[2]), text(r[3]), num(r[4]), time(r[5])));
        return out;
    }

    private boolean restoreDeleted(UUID workspaceId, UUID applicationId, UUID scenarioId) {
        Query find = em.createNativeQuery("select module_name, feature_name, name from core.test_scenario where id = :id and workspace_id = :w and application_id = :a and status = 'DELETED'");
        find.setParameter("id", scenarioId); find.setParameter("w", workspaceId); find.setParameter("a", applicationId);
        List<Object[]> found = rows(find);
        if (found.isEmpty()) return false;
        Object[] r = found.get(0);
        String name = freeName(workspaceId, applicationId, text(r[0]), text(r[1]), String.valueOf(r[2]), "restored");
        Query upd = em.createNativeQuery("update core.test_scenario set status = 'ACTIVE', deleted_at = null, deleted_by = null, name = :n, updated_at = now() where id = :id");
        upd.setParameter("n", name); upd.setParameter("id", scenarioId);
        upd.executeUpdate();
        return true;
    }

    @Transactional
    public RecorderDtos.ScenarioResponse restore(UUID workspaceId, UUID applicationId, UUID scenarioId) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        if (!restoreDeleted(workspaceId, applicationId, scenarioId)) throw new ResourceNotFoundException("Deleted scenario not found.");
        audit.success(workspaceId, "SCENARIO_RESTORED", "TEST_SCENARIO", scenarioId, Map.of("from", "DELETED"));
        em.clear();
        return scenarios.findByIdAndWorkspaceIdAndApplicationId(scenarioId, workspaceId, applicationId)
            .map(this::response).orElseThrow(() -> new ResourceNotFoundException("Scenario not found."));
    }

    /** Permanently removes deleted scenarios (one, or all of them when scenarioId is null). Only scenarios already in "recently deleted" can be removed. */
    @Transactional
    public int purgeDeleted(UUID workspaceId, UUID applicationId, UUID scenarioId) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        String scope = "select id from core.test_scenario where workspace_id = :w and application_id = :a and status = 'DELETED'" + (scenarioId == null ? "" : " and id = :id");
        // The recordings these scenarios came from must not come back in "not saved as a scenario": mark them as dealt with.
        Query dismiss = em.createNativeQuery("update core.recording_session set recovery_dismissed = true where id in "
            + "(select source_recording_session_id from core.scenario_version where source_recording_session_id is not null and scenario_id in (" + scope + "))");
        dismiss.setParameter("w", workspaceId); dismiss.setParameter("a", applicationId);
        if (scenarioId != null) dismiss.setParameter("id", scenarioId);
        dismiss.executeUpdate();
        String[] statements = {
            "delete from core.automation_implementation where scenario_id in (" + scope + ")",
            "delete from core.scenario_version where scenario_id in (" + scope + ")",
            "delete from core.test_scenario where id in (" + scope + ")"
        };
        int removed = 0;
        for (String sql : statements) {
            Query q = em.createNativeQuery(sql);
            q.setParameter("w", workspaceId); q.setParameter("a", applicationId);
            if (scenarioId != null) q.setParameter("id", scenarioId);
            removed = q.executeUpdate();
        }
        if (scenarioId != null && removed == 0) throw new ResourceNotFoundException("Deleted scenario not found. Only a scenario in Recently deleted can be removed permanently.");
        audit.success(workspaceId, "SCENARIO_PURGED", scenarioId == null ? "APPLICATION" : "TEST_SCENARIO", scenarioId == null ? applicationId : scenarioId, Map.of("removed", removed));
        return removed;
    }

    // ---- version history -----------------------------------------------------------------------------------------

    @Transactional(readOnly = true)
    public List<RecoveryDtos.VersionInfo> listVersions(UUID workspaceId, UUID applicationId, UUID scenarioId) {
        guard.requireRead(workspaceId); applications.entity(workspaceId, applicationId);
        scenarios.findByIdAndWorkspaceIdAndApplicationId(scenarioId, workspaceId, applicationId)
            .orElseThrow(() -> new ResourceNotFoundException("Scenario not found."));
        List<ScenarioVersionEntity> all = versions.findByScenarioIdOrderByVersionNoDesc(scenarioId);
        List<RecoveryDtos.VersionInfo> out = new ArrayList<>();
        for (int i = 0; i < all.size(); i++) {
            ScenarioVersionEntity v = all.get(i);
            out.add(new RecoveryDtos.VersionInfo(v.getVersionNo(), v.getCreatedAt() == null ? null : v.getCreatedAt().toString(), v.getSourceRecordingSessionId(), i == 0));
        }
        return out;
    }

    /** Rolls a scenario back to an older version by saving that version again as the newest one; nothing is lost. */
    @Transactional
    public RecorderDtos.ScenarioResponse restoreVersion(UUID workspaceId, UUID applicationId, UUID scenarioId, int versionNo) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        TestScenarioEntity scenario = scenarios.findByIdAndWorkspaceIdAndApplicationId(scenarioId, workspaceId, applicationId)
            .orElseThrow(() -> new ResourceNotFoundException("Scenario not found."));
        ScenarioVersionEntity old = versions.findByScenarioIdAndVersionNo(scenarioId, versionNo)
            .orElseThrow(() -> new ResourceNotFoundException("Scenario version not found."));
        int next = scenario.bumpVersion();
        scenarios.save(scenario);
        versions.save(new ScenarioVersionEntity(scenarioId, next, null, old.getAutomationIr(), currentUser.currentUser().getId()));
        audit.success(workspaceId, "SCENARIO_VERSION_RESTORED", "TEST_SCENARIO", scenarioId, Map.of("restoredVersion", versionNo, "newVersion", next));
        return response(scenario);
    }

    // ---- finished recordings that are not saved as a scenario ----------------------------------------------------

    @Transactional(readOnly = true)
    public List<RecoveryDtos.RecoverableRecording> recoverableRecordings(UUID workspaceId, UUID applicationId) {
        guard.requireRead(workspaceId); applications.entity(workspaceId, applicationId);
        Query q = em.createNativeQuery("select s.id, s.scenario_name, s.module_name, s.feature_name, s.created_at from core.recording_session s "
            + "where s.workspace_id = :w and s.application_id = :a and s.status = 'COMPLETED' and s.ir_json is not null and s.ir_json <> '' "
            + "and s.recovery_dismissed = false and not exists (select 1 from core.scenario_version v where v.source_recording_session_id = s.id) order by s.created_at desc limit 100");
        q.setParameter("w", workspaceId); q.setParameter("a", applicationId);
        List<RecoveryDtos.RecoverableRecording> out = new ArrayList<>();
        for (Object[] r : rows(q)) out.add(new RecoveryDtos.RecoverableRecording(uuid(r[0]), text(r[1]), text(r[2]), text(r[3]), time(r[4])));
        return out;
    }

    /** Removes a recording from the "not saved as a scenario" list without recovering it. The recording itself is kept. */
    @Transactional
    public void dismissRecording(UUID workspaceId, UUID applicationId, UUID sessionId) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        Query q = em.createNativeQuery("update core.recording_session set recovery_dismissed = true where id = :id and workspace_id = :w and application_id = :a");
        q.setParameter("id", sessionId); q.setParameter("w", workspaceId); q.setParameter("a", applicationId);
        if (q.executeUpdate() == 0) throw new ResourceNotFoundException("Recording not found.");
        audit.success(workspaceId, "RECORDING_DISMISSED", "RECORDING_SESSION", sessionId, Map.of("applicationId", applicationId));
    }

    // ---- backup file ---------------------------------------------------------------------------------------------

    @Transactional(readOnly = true)
    public JsonNode backup(UUID workspaceId, UUID applicationId) {
        guard.requireRead(workspaceId); applications.entity(workspaceId, applicationId);
        return buildBackup(workspaceId, applicationId);
    }

    ObjectNode buildBackup(UUID workspaceId, UUID applicationId) {
        ObjectNode root = mapper.createObjectNode();
        root.put("format", "aqea-scenarios");
        root.put("formatVersion", 1);
        root.put("exportedAt", Instant.now().toString());
        root.put("applicationId", applicationId.toString());
        ArrayNode list = root.putArray("scenarios");
        Query q = em.createNativeQuery("select id, module_name, feature_name, name, status, current_version, execution_order from core.test_scenario "
            + "where workspace_id = :w and application_id = :a order by execution_order nulls last, name");
        q.setParameter("w", workspaceId); q.setParameter("a", applicationId);
        for (Object[] r : rows(q)) {
            ObjectNode s = list.addObject();
            UUID id = uuid(r[0]);
            s.put("id", id.toString());
            s.put("moduleName", text(r[1]));
            s.put("featureName", text(r[2]));
            s.put("name", text(r[3]));
            s.put("status", text(r[4]));
            s.put("currentVersion", num(r[5]));
            if (r[6] != null) s.put("executionOrder", num(r[6]));
            ArrayNode vs = s.putArray("versions");
            Query vq = em.createNativeQuery("select version_no, automation_ir, created_at from core.scenario_version where scenario_id = :id order by version_no");
            vq.setParameter("id", id);
            for (Object[] v : rows(vq)) {
                ObjectNode o = vs.addObject();
                o.put("versionNo", num(v[0]));
                o.put("createdAt", time(v[2]));
                try { o.set("automationIr", mapper.readTree(String.valueOf(v[1]))); }
                catch (RuntimeException ex) { o.put("automationIrText", String.valueOf(v[1])); }
            }
        }
        return root;
    }

    /** Writes a backup file after a change. Does nothing unless SCENARIO_BACKUP_DIR is set; never fails the request. */
    @Transactional(readOnly = true)
    public void snapshotQuietly(UUID workspaceId, UUID applicationId) {
        if (backupDir == null || backupDir.isBlank()) return;
        try {
            Path dir = Path.of(backupDir);
            Files.createDirectories(dir);
            String json = mapper.writeValueAsString(buildBackup(workspaceId, applicationId));
            Files.writeString(dir.resolve("scenarios-" + applicationId + "-latest.json"), json);
            String stamp = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss-SSS").format(LocalDateTime.now(ZoneOffset.UTC));
            Files.writeString(dir.resolve("scenarios-" + applicationId + "-" + stamp + ".json"), json);
            String prefix = "scenarios-" + applicationId + "-2";
            try (Stream<Path> files = Files.list(dir)) {
                List<Path> old = files.filter(p -> p.getFileName().toString().startsWith(prefix)).sorted(java.util.Comparator.reverseOrder()).skip(KEEP_SNAPSHOTS).toList();
                for (Path p : old) Files.deleteIfExists(p);
            }
        } catch (Exception ex) {
            log.warn("Scenario backup file could not be written: {}", ex.getMessage());
        }
    }

    // ---- import --------------------------------------------------------------------------------------------------

    /**
     * Brings back whatever a backup file holds that is missing: deleted scenarios, scenarios that are gone, and missing versions. Never overwrites.
     * A backup made in another workspace or application (for example by another user) is copied in under new ids, so anybody can load it.
     */
    @Transactional
    public RecoveryDtos.ImportResult importBackup(UUID workspaceId, UUID applicationId, JsonNode doc) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        if (doc == null || !"aqea-scenarios".equals(doc.path("format").asText()) || !doc.path("scenarios").isArray()) {
            throw new IllegalArgumentException("This file is not a scenario backup.");
        }
        UUID user = currentUser.currentUser().getId();
        int restored = 0, created = 0, copied = 0, added = 0, skipped = 0;
        for (JsonNode s : doc.path("scenarios")) {
            UUID id;
            try { id = UUID.fromString(s.path("id").asText()); }
            catch (RuntimeException ex) { skipped++; continue; }
            String module = str(s.path("moduleName")), feature = str(s.path("featureName")), name = str(s.path("name"));
            if (name == null) { skipped++; continue; }
            String status = "DELETED".equals(s.path("status").asText()) ? "DELETED" : "ACTIVE";
            Query exists = em.createNativeQuery("select status, workspace_id, application_id from core.test_scenario where id = :id");
            exists.setParameter("id", id);
            List<Object[]> found = rows(exists);
            boolean copy = false;
            if (!found.isEmpty()) {
                Object[] e = found.get(0);
                if (workspaceId.equals(uuid(e[1])) && applicationId.equals(uuid(e[2]))) {
                    if ("DELETED".equals(text(e[0])) && "ACTIVE".equals(status) && restoreDeleted(workspaceId, applicationId, id)) restored++;
                    added += addMissingVersions(id, s.path("versions"), user, null);
                    continue;
                }
                // The backup comes from another workspace or application (for example another user's): make a copy here under a new id.
                if ("DELETED".equals(status) || taken(workspaceId, applicationId, module, feature, name)) { skipped++; continue; }
                id = UUID.randomUUID();
                copy = true;
            }
            String finalName = "ACTIVE".equals(status) ? freeName(workspaceId, applicationId, module, feature, name, "recovered") : name;
            int order = s.path("executionOrder").isNumber() ? s.path("executionOrder").asInt() : nextOrder(workspaceId, applicationId);
            Query ins = em.createNativeQuery("insert into core.test_scenario (id, workspace_id, application_id, module_name, feature_name, name, status, current_version, execution_order, created_by, created_at, updated_at) "
                + "values (:id, :w, :a, nullif(:m, ''), nullif(:f, ''), :n, :st, 1, :ord, :by, now(), now())");
            ins.setParameter("id", id); ins.setParameter("w", workspaceId); ins.setParameter("a", applicationId);
            ins.setParameter("m", blank(module)); ins.setParameter("f", blank(feature)); ins.setParameter("n", finalName);
            ins.setParameter("st", status); ins.setParameter("ord", order); ins.setParameter("by", user);
            ins.executeUpdate();
            if ("DELETED".equals(status)) {
                Query del = em.createNativeQuery("update core.test_scenario set deleted_at = now(), deleted_by = :by where id = :id");
                del.setParameter("by", user); del.setParameter("id", id); del.executeUpdate();
            }
            added += addMissingVersions(id, s.path("versions"), user, copy ? id.toString() : null);
            if (copy) copied++; else created++;
        }
        audit.success(workspaceId, "SCENARIO_BACKUP_IMPORTED", "APPLICATION", applicationId,
            Map.of("restored", restored, "created", created, "copied", copied, "versionsAdded", added, "skipped", skipped));
        return new RecoveryDtos.ImportResult(restored, created, copied, added, skipped);
    }

    private int nextOrder(UUID workspaceId, UUID applicationId) {
        Query q = em.createNativeQuery("select coalesce(max(execution_order), 0) + 1 from core.test_scenario where workspace_id = :w and application_id = :a");
        q.setParameter("w", workspaceId); q.setParameter("a", applicationId);
        return ((Number) q.getSingleResult()).intValue();
    }

    private int addMissingVersions(UUID scenarioId, JsonNode list, UUID user, String rewriteScenarioId) {
        int added = 0;
        if (list == null || !list.isArray()) return 0;
        for (JsonNode v : list) {
            int no = v.path("versionNo").asInt(0);
            JsonNode ir = v.path("automationIr");
            if (rewriteScenarioId != null && ir.isObject() && ir.path("scenario").isObject()) ((ObjectNode) ir.path("scenario")).put("id", rewriteScenarioId);
            String irText = ir.isObject() ? mapper.writeValueAsString(ir) : str(v.path("automationIrText"));
            if (no <= 0 || irText == null) continue;
            Query c = em.createNativeQuery("select count(*) from core.scenario_version where scenario_id = :id and version_no = :no");
            c.setParameter("id", scenarioId); c.setParameter("no", no);
            if (((Number) c.getSingleResult()).longValue() > 0) continue;
            Query ins = em.createNativeQuery("insert into core.scenario_version (id, scenario_id, version_no, automation_ir, created_by, created_at) values (:id, :s, :no, :ir, :by, now())");
            ins.setParameter("id", UUID.randomUUID()); ins.setParameter("s", scenarioId); ins.setParameter("no", no);
            ins.setParameter("ir", irText); ins.setParameter("by", user);
            ins.executeUpdate();
            added++;
        }
        Query cur = em.createNativeQuery("update core.test_scenario set current_version = greatest(current_version, coalesce((select max(version_no) from core.scenario_version where scenario_id = :id), 1)) where id = :id");
        cur.setParameter("id", scenarioId);
        cur.executeUpdate();
        return added;
    }
}
