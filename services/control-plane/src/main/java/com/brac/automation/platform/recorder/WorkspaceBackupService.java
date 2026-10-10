package com.brac.automation.platform.recorder;

import com.brac.automation.platform.audit.AuditService;
import com.brac.automation.platform.security.CurrentUserService;
import com.brac.automation.platform.workspace.WorkspaceAccessGuard;
import com.brac.automation.platform.workspace.WorkspaceDtos;
import com.brac.automation.platform.workspace.WorkspaceService;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.Query;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

/**
 * Whole-workspace backup: the workspace, its applications, their environments (names and URLs, never passwords) and every scenario with all versions.
 * Loading it into a brand new workspace gives a new user a ready-made setup; loading it into an existing workspace only adds what is missing.
 */
@Service
public class WorkspaceBackupService {
    @PersistenceContext
    private EntityManager em;

    private final ScenarioRecoveryService recovery;
    private final WorkspaceService workspaceService;
    private final WorkspaceAccessGuard guard;
    private final CurrentUserService currentUser;
    private final AuditService audit;
    private final ObjectMapper mapper;

    public WorkspaceBackupService(ScenarioRecoveryService recovery, WorkspaceService workspaceService, WorkspaceAccessGuard guard,
                                  CurrentUserService currentUser, AuditService audit, ObjectMapper mapper) {
        this.recovery = recovery; this.workspaceService = workspaceService; this.guard = guard;
        this.currentUser = currentUser; this.audit = audit; this.mapper = mapper;
    }

    @SuppressWarnings("unchecked")
    private static List<Object[]> rows(Query q) { return (List<Object[]>) q.getResultList(); }
    private static UUID uuid(Object o) { return UUID.fromString(String.valueOf(o)); }
    private static String text(Object o) { return o == null ? null : String.valueOf(o); }
    private static String str(JsonNode n) {
        if (n == null || n.isNull() || n.isMissingNode()) return null;
        String v = n.asText();
        return v == null || v.isBlank() ? null : v.trim();
    }

    @Transactional(readOnly = true)
    public JsonNode backup(UUID workspaceId) {
        guard.requireRead(workspaceId);
        WorkspaceDtos.Response w = workspaceService.get(workspaceId);
        ObjectNode root = mapper.createObjectNode();
        root.put("format", "aqea-workspace");
        root.put("formatVersion", 1);
        root.put("exportedAt", Instant.now().toString());
        ObjectNode ws = root.putObject("workspace");
        ws.put("key", w.key()); ws.put("name", w.name()); ws.put("description", w.description());
        ArrayNode apps = root.putArray("applications");
        Query aq = em.createNativeQuery("select id, name, description from core.application where workspace_id = :w and status = 'ACTIVE' order by name");
        aq.setParameter("w", workspaceId);
        for (Object[] a : rows(aq)) {
            UUID appId = uuid(a[0]);
            ObjectNode app = apps.addObject();
            app.put("name", text(a[1])); app.put("description", text(a[2]));
            ArrayNode envs = app.putArray("environments");
            Query eq = em.createNativeQuery("select name, base_url, default_browser, headless_default, allow_recording, allow_execution from core.environment "
                + "where application_id = :a and status = 'ACTIVE' order by name");
            eq.setParameter("a", appId);
            for (Object[] e : rows(eq)) {
                ObjectNode env = envs.addObject();
                env.put("name", text(e[0])); env.put("baseUrl", text(e[1])); env.put("defaultBrowser", text(e[2]));
                env.put("headlessDefault", Boolean.TRUE.equals(e[3])); env.put("allowRecording", Boolean.TRUE.equals(e[4])); env.put("allowExecution", Boolean.TRUE.equals(e[5]));
            }
            app.set("scenarios", recovery.buildBackup(workspaceId, appId).path("scenarios"));
        }
        return root;
    }

    /** Creates a new workspace (the caller becomes its administrator) from a workspace backup. */
    @Transactional
    public RecoveryDtos.WorkspaceImportResult importAsNewWorkspace(JsonNode doc) {
        check(doc);
        JsonNode meta = doc.path("workspace");
        String name = str(meta.path("name")) == null ? "Imported workspace" : str(meta.path("name"));
        String key = freeKey(str(meta.path("key")) == null ? "IMPORTED" : str(meta.path("key")));
        WorkspaceDtos.Response created = workspaceService.create(new WorkspaceDtos.CreateRequest(
            name.length() > 200 ? name.substring(0, 200) : name, key, str(meta.path("description"))));
        return load(created.id(), created.key(), created.name(), doc);
    }

    /** Adds the applications, environments and scenarios that are missing to an existing workspace. Never overwrites. */
    @Transactional
    public RecoveryDtos.WorkspaceImportResult importIntoWorkspace(UUID workspaceId, JsonNode doc) {
        guard.requireWrite(workspaceId);
        check(doc);
        WorkspaceDtos.Response w = workspaceService.get(workspaceId);
        return load(workspaceId, w.key(), w.name(), doc);
    }

    private static void check(JsonNode doc) {
        if (doc == null || !"aqea-workspace".equals(doc.path("format").asText()) || !doc.path("applications").isArray())
            throw new IllegalArgumentException("This file is not a workspace backup. Use a file made with \"Download workspace backup\".");
    }

    private String freeKey(String wanted) {
        String base = wanted.toUpperCase(Locale.ROOT).replaceAll("[^A-Z0-9_-]", "");
        base = base.replaceFirst("^[_-]+", "");
        if (base.length() < 2) base = "IMPORTED";
        if (base.length() > 34) base = base.substring(0, 34);
        String key = base;
        for (int n = 2; n < 1000 && keyTaken(key); n++) key = base + "-" + n;
        return key;
    }

    private boolean keyTaken(String key) {
        Query q = em.createNativeQuery("select count(*) from core.workspace where upper(workspace_key) = :k");
        q.setParameter("k", key.toUpperCase(Locale.ROOT));
        return ((Number) q.getSingleResult()).longValue() > 0;
    }

    private RecoveryDtos.WorkspaceImportResult load(UUID workspaceId, String key, String name, JsonNode doc) {
        UUID user = currentUser.currentUser().getId();
        int appsCreated = 0, envsCreated = 0, restored = 0, created = 0, copied = 0, versions = 0, skipped = 0;
        for (JsonNode a : doc.path("applications")) {
            String appName = str(a.path("name"));
            if (appName == null) continue;
            UUID appId = findApp(workspaceId, appName);
            if (appId == null) {
                appId = UUID.randomUUID();
                Query ins = em.createNativeQuery("insert into core.application (id, workspace_id, name, description, status, created_by, created_at, updated_at) "
                    + "values (:id, :w, :n, :d, 'ACTIVE', :by, now(), now())");
                ins.setParameter("id", appId); ins.setParameter("w", workspaceId); ins.setParameter("n", appName);
                ins.setParameter("d", str(a.path("description"))); ins.setParameter("by", user);
                ins.executeUpdate();
                appsCreated++;
            }
            for (JsonNode e : a.path("environments")) {
                String envName = str(e.path("name")), url = str(e.path("baseUrl"));
                if (envName == null || url == null) continue;
                Query c = em.createNativeQuery("select count(*) from core.environment where application_id = :a and lower(btrim(name)) = :n");
                c.setParameter("a", appId); c.setParameter("n", envName.toLowerCase(Locale.ROOT));
                if (((Number) c.getSingleResult()).longValue() > 0) continue;
                Query ins = em.createNativeQuery("insert into core.environment (id, application_id, name, base_url, default_browser, headless_default, allow_recording, allow_execution, validation_status, status, created_by, created_at, updated_at) "
                    + "values (:id, :a, :n, :u, :b, :h, :r, :x, 'UNVERIFIED', 'ACTIVE', :by, now(), now())");
                ins.setParameter("id", UUID.randomUUID()); ins.setParameter("a", appId); ins.setParameter("n", envName); ins.setParameter("u", url);
                ins.setParameter("b", str(e.path("defaultBrowser")) == null ? "CHROMIUM" : str(e.path("defaultBrowser")));
                ins.setParameter("h", e.path("headlessDefault").asBoolean(true)); ins.setParameter("r", e.path("allowRecording").asBoolean(true));
                ins.setParameter("x", e.path("allowExecution").asBoolean(true)); ins.setParameter("by", user);
                ins.executeUpdate();
                envsCreated++;
            }
            ObjectNode appDoc = mapper.createObjectNode();
            appDoc.put("format", "aqea-scenarios");
            appDoc.set("scenarios", a.path("scenarios").isArray() ? a.path("scenarios") : mapper.createArrayNode());
            RecoveryDtos.ImportResult r = recovery.importBackup(workspaceId, appId, appDoc);
            restored += r.restored(); created += r.created(); copied += r.copied(); versions += r.versionsAdded(); skipped += r.skipped();
        }
        RecoveryDtos.ImportResult total = new RecoveryDtos.ImportResult(restored, created, copied, versions, skipped);
        audit.success(workspaceId, "WORKSPACE_BACKUP_IMPORTED", "WORKSPACE", workspaceId,
            Map.of("applicationsCreated", appsCreated, "environmentsCreated", envsCreated, "scenarios", created + copied + restored));
        return new RecoveryDtos.WorkspaceImportResult(workspaceId, key, name, appsCreated, envsCreated, total);
    }

    private UUID findApp(UUID workspaceId, String name) {
        Query q = em.createNativeQuery("select id from core.application where workspace_id = :w and lower(btrim(name)) = :n");
        q.setParameter("w", workspaceId); q.setParameter("n", name.toLowerCase(Locale.ROOT));
        List<?> found = q.getResultList();
        return found.isEmpty() ? null : UUID.fromString(String.valueOf(found.get(0)));
    }
}
